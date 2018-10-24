import gevent
import gevent.monkey

gevent.monkey.patch_all()

import time, logging, sys, argparse, socket, struct
from JumpScale import j
from gevent.lock import RLock

OFFLINE_STATES = ["MAINTENANCE", "DECOMMISSION"]
FORMAT = "%(asctime)s -  [%(levelname)s] - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)


class CacheDict(dict):
    def __init__(self, default_age=60, **kwargs):
        self.default_age = default_age
        for key, value in kwargs.items():
            self.__setitem__(key, value)
        super(CacheDict, self).__init__(self)

    def _check_expired(self):
        for key, value in self.copy().items():
            if value[1] > 0:
                if time.time() - value[2] > value[1]:
                    return super(CacheDict, self).__delitem__(key)

    def __setitem__(self, key, value, age=None):
        age = age if age is not None else self.default_age
        value = (value, age, time.time())
        return super(CacheDict, self).__setitem__(key, value)

    def __getitem__(self, key):
        self._check_expired()
        value, _, _ = super(CacheDict, self).__getitem__(key)
        return value

    def __repr__(self):
        self._check_expired()
        return repr({k: v for k, v in self.items()})

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def set(self, key, value, age=None):
        self.__setitem__(key, value, age)

    def items(self):
        self._check_expired()
        return [(k, v[0]) for k, v in dict.items(self)]

    def values(self):
        self._check_expired()
        return [v[0] for v in dict.values(self)]


class UptimeMonitor(object):
    def __init__(self, ip, port, cache_timeout, alerts_max_age):
        self.ip = ip
        self.port = port
        self.cache_timeout = cache_timeout
        self.alerts_max_age = alerts_max_age
        self._alerts = dict()
        self._scheduled_jobs = set()
        self._offline_nodes = set()
        self._nodes_cache = CacheDict(default_age=cache_timeout)
        self.scl = j.clients.osis.getNamespace("system")
        self.acl = j.clients.agentcontroller.get()
        self.socket = socket.socket(type=socket.SOCK_DGRAM)
        self.ping_socket = socket.socket(type=socket.SOCK_STREAM)
        self.lock = RLock()
        self._initialize()

    def get_nodes(self, cache=True):
        cached_nodes = self._nodes_cache.get("info")
        if not cached_nodes or not cache:
            nodes = self.scl.node.search(
                {
                    "$fields": ["guid", "name", "status"],
                    "roles": {"$in": ["cpunode", "storagenode"]},
                }
            )
            cached_nodes = dict(list([(node["guid"], node) for node in nodes[1:]]))
            self._nodes_cache["info"] = cached_nodes

        return cached_nodes

    def _handler(self, data, address):
        nodes = self.get_nodes()
        gid, aid, nid, state = struct.unpack("lllb", data)
        node_guid = "%s_%s" % (gid, nid)
        alerter_guid = "%s_%s" % (gid, aid)

        if node_guid not in nodes or alerter_guid not in nodes:
            nodes = self.get_nodes(cache=False)

        if nodes[alerter_guid]["status"] in OFFLINE_STATES:
            logging.info(
                "Skip alert from node: %s, cause it is not enabled", alerter_guid
            )
            return

        if nodes[node_guid]["status"] in OFFLINE_STATES:
            logging.info(
                "Skip the investigation of node: %s, cause it is not enabled", node_guid
            )
            return

        if not self._alerts.get(node_guid):
            self._alerts[node_guid] = CacheDict()
        self._alerts[node_guid][alerter_guid] = bool(state)

        if state:
            logging.info("Alerter: %s - Node: %s is UP", alerter_guid, node_guid)
            if node_guid in self._offline_nodes:
                if all(self._alerts[node_guid].values()):
                    self._offline_nodes.remove(node_guid)
            return
        else:
            logging.error("Alerter: %s - Node: %s is DOWN", alerter_guid, node_guid)

        if node_guid in self._scheduled_jobs or node_guid in self._offline_nodes:
            logging.info(
                "Skip the new investigation of node: %s, cause it is already being processed",
                node_guid,
            )
            return

        with self.lock:
            self._scheduled_jobs.add(node_guid)
            try:
                failures = self._alerts[node_guid].values().count(False)
                active_nodes = [node["status"] for node in nodes.values()].count(
                    "ENABLED"
                )
                if failures > active_nodes / 2:
                    logging.info("Investigating Node: %s", node_guid)
                    self._investigate_node(node_guid)
            finally:
                self._scheduled_jobs.remove(node_guid)

    def _investigate_node(self, node_guid):
        gid, nid = node_guid.split("_")
        job_info = self.acl.executeJumpscript(
            "jumpscale",
            "node_maintenance_2",
            gid=gid,
            role="controller",
            args={"nid": nid},
            wait=True,
        )
        if job_info["state"] != "OK":
            logging.error(
                "Error while investigating node %s, job id is %s",
                node_guid,
                job_info["guid"],
            )
        else:
            self._offline_nodes.add(node_guid)
            self._alerts[node_guid].clear()

    def ping(self):
        while True:
            self.ping_socket.accept()

    def _initialize(self):
        self.socket.bind((self.ip, self.port))
        self.ping_socket.bind((self.ip, self.port))
        self.ping_socket.listen(1)

    def start(self):
        gevent.spawn(self.ping)
        while True:
            data, address = self.socket.recvfrom(25)
            gevent.spawn(self._handler, data=data, address=address)

    def stop(self):
        self.socket.close()
        self.ping_socket.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--ip", default="")
    parser.add_argument("-p", "--port", type=int, default=9500)
    parser.add_argument("-c", "--cache-timeout", type=int, default=300)
    parser.add_argument("-g", "--alerts-max-age", type=int, default=60)
    args = parser.parse_args()

    monitor = UptimeMonitor(
        ip=args.ip,
        port=args.port,
        cache_timeout=args.cache_timeout,
        alerts_max_age=args.alerts_max_age,
    )

    try:
        monitor.start()
    except KeyboardInterrupt:
        monitor.stop()
