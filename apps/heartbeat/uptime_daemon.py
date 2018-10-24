import uuid, logging, sys, gevent, argparse, netaddr, time, struct
from gevent import socket
from JumpScale import j

MSG_SIZE = 16
FORMAT = "%(asctime)s -  [%(levelname)s] - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=FORMAT)


class UptimeDaemon(object):
    def __init__(self, port, interval, timeout, interfaces):
        self.port = port
        self.interval = interval
        self.timeout = timeout
        self.interfaces = interfaces
        self.gid = j.application.whoAmI.gid
        self.nid = j.application.whoAmI.nid
        self.guid = "{}_{}".format(self.gid, self.nid)
        self.scl = j.clients.osis.getNamespace("system")
        self.monitor_addr = (self._get_controller_ip(), self.port)

    def _get_controller_ip(self):
        nodes = self.scl.node.search({"roles": {"$in": ["controllernode"]}})[1:]
        for node in nodes:
            ipaddr = [
                nic["ip"][0] for nic in node["netaddr"] if nic["name"] == "backplane1"
            ][0]
            if j.system.net.ping(ipaddr).get("received"):
                return ipaddr
        else:
            raise RuntimeError("Couldn't connect to uptime monitor")

    def _get_network(self, interface):
        if interface == "management":
            interface, _ = j.system.net.getDefaultIPConfig()

        networks = j.system.net.getNetworkInfo()
        for network in networks:
            if network["name"] == interface:
                subnet = "{}/{}".format(network["ip"][0], network["cidr"][0])
                network = netaddr.IPNetwork(subnet)
                return network

    def _get_network_ip(self, ipaddrs, network):
        for ipaddr in ipaddrs:
            if ipaddr in network:
                return ipaddr

    @property
    def nodes(self):
        nodes = self.scl.node.search(
            {
                "gid": self.gid,
                "id": {"$ne": self.nid},
                "$fields": ["id", "name", "ipaddr"],
                "roles": {"$in": ["cpunode", "storagenode"]},
            }
        )
        return nodes[1:]

    def _ping_handler(self, node, address, interface):
        sock = socket.socket(type=socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        log_msg = "[%s] Node: %s - Interface: %s" % ("%s", node["name"], interface)
        while True:
            start_time = time.time()
            state = None
            logging.info(log_msg, "PING")
            msg = uuid.uuid4().bytes
            sock.sendto(msg[:MSG_SIZE], address)
            try:
                recv_msg, _ = sock.recvfrom(MSG_SIZE)
                if msg != recv_msg:
                    state = False
                else:
                    state = True
                    logging.info(log_msg, "ACK")

            except socket.timeout:
                state = False
                logging.error(log_msg, "NAK")

            except Exception as e:
                logging.error("Unexpected error: %s", str(e))

            finally:
                if state is not None:
                    data = struct.pack("lllb", self.gid, self.nid, node["id"], state)
                    sock.sendto(data, self.monitor_addr)

            exec_time = time.time() - start_time
            gevent.sleep(self.interval - exec_time)

    def _ack_handler(self, sock):
        while True:
            data, address = sock.recvfrom(MSG_SIZE)
            sock.sendto(data, address)

    def start(self):
        jobs = []
        for interface in self.interfaces:
            network = self._get_network(interface)
            if not network:
                raise RuntimeError("Couldn't find network {}".format(interface))

            sock = socket.socket(type=socket.SOCK_DGRAM)
            sock.bind((network.ip.format(), self.port))
            jobs.append(gevent.spawn(self._ack_handler, sock))

            for node in self.nodes:
                ip = self._get_network_ip(node["ipaddr"], network)
                address = (ip, self.port)
                jobs.append(
                    gevent.spawn(
                        self._ping_handler,
                        node=node,
                        address=address,
                        interface=interface,
                    )
                )

        gevent.joinall(jobs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=9500)
    parser.add_argument("-i", "--interval", type=float, default=1)
    parser.add_argument("-t", "--timeout", type=float, default=5)
    parser.add_argument(
        "-f", "--interfaces", nargs="+", default=["backplane1", "management"]
    )
    args = parser.parse_args()

    ud = UptimeDaemon(
        port=args.port,
        interval=args.interval,
        timeout=args.timeout,
        interfaces=args.interfaces,
    )
    ud.start()
