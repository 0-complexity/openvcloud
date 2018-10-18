from JumpScale import j
from JumpScale.lib.ovsnetconfig.VXNet import utils
from CloudscalerLibcloud.utils.libvirtutil import LibvirtUtil
from CloudscalerLibcloud.utils.network import Network, NetworkTool
import os
import subprocess
import json
import shutil
import jinja2
import netaddr
import copy


def get(templatename):
    templatepath = os.path.dirname(__file__)
    loader = jinja2.FileSystemLoader(templatepath)
    env = jinja2.Environment(loader=loader)
    return env.get_template(templatename)


def render(templatename, **kwargs):
    env = get(templatename)
    return env.render(**kwargs) + "\n"


class Gateway(object):
    def __init__(self, vfwobj):
        self.leases = vfwobj.get("leases") or []
        self.privatenetwork = netaddr.IPNetwork(vfwobj["privatenetwork"])
        self.privateip = netaddr.IPNetwork(
            "{}/{}".format(
                netaddr.IPAddress(self.privatenetwork.first + 1),
                self.privatenetwork.prefixlen,
            )
        )
        self.portforwards = vfwobj.get("tcpForwardRules") or []
        self.proxies = vfwobj.get("wsForwardRules") or []
        self.cloudinit = vfwobj.get("cloud-init") or []
        self.networkid = vfwobj["id"]
        self.external = vfwobj["external"]
        self.name = "gw-{:04x}".format(self.networkid)
        self.services = ("dnsmasq", "caddy", "cloud-init")
        self.connection = LibvirtUtil()
        self.networkutil = Network(self.connection)

    def namespace_exists(self):
        return self.name in utils.get_all_namespaces()

    def _create_network_namespace(self):
        netinfo = [{"id": self.networkid, "type": "vxlan"}]
        with NetworkTool(netinfo, self.connection):
            vxnet = j.system.ovsnetconfig.ensureVXNet(self.networkid, "vxbackend")
            j.system.ovsnetconfig.connectInNameSpace(
                vxnet.bridge.name, self.name, str(self.privateip), name="private"
            )
        netinfo = [{"id": self.external["vlan"], "type": "vlan"}]
        with NetworkTool(netinfo, self.connection):
            bridgename = j.system.ovsnetconfig.createExtNetwork(self.external["vlan"])
            if not self.connection.checkNetwork(bridgename):
                self.connection.createNetwork(bridgename, bridgename)
            gateway = self.external["gateway"]
            j.system.ovsnetconfig.connectInNameSpace(
                bridgename, self.name, self.external["ips"][0], gateway, "public"
            )
        j.system.process.execute(
            "ip -n {} address add 169.254.169.254/32 dev lo".format(self.name)
        )

    def start(self):
        if self.is_running():
            self.apply_firewall_rules()
            self.update_leases()
            self.update_proxies()
            self.update_cloud_init()
            return
        try:
            self.destroy()
            self._create_network_namespace()
            self._prepare_bundle("dnsmasq")
            self.install_service("dnsmasq")
            self.update_leases()
            self.apply_firewall_rules()
            self.update_proxies()
            self.update_cloud_init()
        except:
            self.destroy()
            raise

    def get_service_path(self, service):
        return "/var/lib/runc/{}/{}".format(self.name, service)

    def update_leases(self):
        config = render(
            "dnsmasq.conf", leases=self.leases, privateip=str(self.privateip.ip)
        )
        servicepath = self.get_service_path("dnsmasq")
        configpath = os.path.join(servicepath, "rootfs", "etc", "dnsmasq.conf")
        with open(configpath, "w+") as fd:
            fd.write(config)
        servicename = "{}-{}".format(self.name, "dnsmasq")
        j.system.platform.ubuntu.restartService(servicename)

    def _prepare_bundle(self, service):
        servicepath = self.get_service_path(service)
        if not os.path.exists(servicepath):
            templatepath = "/var/lib/runc/templates/{}".format(service)
            j.system.fs.createDir(os.path.dirname(servicepath))
            shutil.copytree(templatepath, servicepath, True)
            contconfigpath = os.path.join(servicepath, "config.json")
            with open(contconfigpath) as fd:
                config = json.load(fd)
            for namespace in config["linux"]["namespaces"]:
                if namespace["type"] == "network":
                    namespace["path"] = "/var/run/netns/{}".format(self.name)
            with open(contconfigpath, "w") as fd:
                json.dump(config, fd)
        return servicepath

    def update_cloud_init(self):
        service = "cloud-init"
        servicepath = self._prepare_bundle(service)
        allcloudinits = copy.deepcopy(self.cloudinit)
        cloudinitpath = os.path.join(servicepath, "rootfs/etc/cloud-init")
        if allcloudinits:
            j.system.fs.createDir(cloudinitpath)
        for cloudinit in allcloudinits:
            mac = cloudinit.pop("mac")
            path = os.path.join(cloudinitpath, mac)
            with open(path, "w+") as fd:
                json.dump(cloudinit, fd)
        self.install_service(service)
        self.start_service(service)

    def update_proxies(self):
        service = "caddy"
        proxies = self.proxies[:]
        proxies.append(
            {
                "protocols": ["http"],
                "host": "169.254.169.254",
                "destinations": ["http://127.0.0.1:8080"],
            }
        )
        servicepath = self._prepare_bundle(service)
        config = render("caddy.conf", proxies=proxies)
        with open(os.path.join(servicepath, "rootfs", "etc", "caddy.conf"), "w+") as fd:
            fd.write(config)
        self.install_service(service)
        self.restart_service(service)

    def restart_service(self, service):
        servicename = "{}-{}".format(self.name, service)
        j.system.platform.ubuntu.restartService(servicename)

    def start_service(self, service):
        servicename = "{}-{}".format(self.name, service)
        j.system.platform.ubuntu.restartService(servicename)

    def service_status(self, service):
        servicename = "{}-{}".format(self.name, service)
        return j.system.platform.ubuntu.statusService(servicename)

    def install_service(self, service):
        servicename = "{}-{}".format(self.name, service)
        if not j.system.platform.ubuntu.statusService(servicename):
            servicepath = self.get_service_path(service)
            j.system.platform.ubuntu.serviceInstall(
                servicename,
                "/usr/sbin/runc",
                "run {}".format(servicename),
                pwd=servicepath,
            )

    def apply_firewall_rules(self):
        servicepath = self.get_service_path("nft")
        servicename = "{}-{}".format(self.name, "nft")
        if not os.path.exists(servicepath):
            self._prepare_bundle("nft")
        ipnet = netaddr.IPNetwork(self.external["ips"][0])
        publicnetwork = {
            "iface": "public",
            "ip": str(ipnet.ip),
            "cidr": str(ipnet.cidr),
        }
        privatenetwork = {"iface": "private", "cidr": str(self.privatenetwork)}
        tempargs = {
            "publicnetwork": publicnetwork,
            "privatenetworks": [privatenetwork],
            "portforwards": self.portforwards,
            "enableproxy": bool(self.proxies)
        }
        config = render("nftables.conf", **tempargs)

        with open(
            os.path.join(servicepath, "rootfs", "etc", "nftables.conf"), "w+"
        ) as fd:
            fd.write(config)
        proc = subprocess.Popen(["runc", "run", "exec", servicename], cwd=servicepath)
        proc.wait()

    def is_running(self):
        servicename = "{}-{}".format(self.name, "dnsmasq")
        return j.system.platform.ubuntu.statusService(servicename)

    def _get_iface_by_index(self, index, networkinfo=None):
        networkinfo = networkinfo or j.system.net.getNetworkInfo()
        for network in networkinfo:
            if network["index"] == index:
                return network

    def destroy(self):
        if self.name in utils.get_all_namespaces():
            # cleanup interfaces
            nsfaces = j.system.net.getNetworkInfo(namespace=self.name)
            ifaces = j.system.net.getNetworkInfo()
            peers = []
            for iface in nsfaces:
                if iface["name"] == "lo":
                    continue
                peerindex = utils.get_peer(iface["name"], self.name)
                peer = self._get_iface_by_index(peerindex, ifaces)
                peers.append(peer["name"])
            for bridge in utils.get_all_bridges():
                connections = utils.listBridgeConnections(bridge)
                for peer in peers[:]:
                    if peer in connections:
                        utils.removeIfFromBridge(bridge, peer)
                        peers.remove(peer)

        for service in self.services:
            self.uninstall_service(service)
        utils.destroyNameSpace(self.name)
        j.system.ovsnetconfig.cleanupIfUnused(self.networkid)
        j.system.ovsnetconfig.cleanupIfUnusedVlanBridge(vlan=self.external["vlan"])
        servicepath = self.get_service_path("")
        j.system.fs.removeDirTree(servicepath)

    def uninstall_service(self, service):
        servicename = "{}-{}".format(self.name, service)
        j.system.platform.ubuntu.stopService(servicename)
        j.system.platform.ubuntu.serviceUninstall(servicename)
        servicepath = self.get_service_path(service)
        j.system.fs.removeDirTree(servicepath)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", default="172.17.2.100/16")
    parser.add_argument("--gateway", default="172.17.0.1")
    parser.add_argument("--vlan", default=0, type=int)
    parser.add_argument("--privatenetwork", default="192.168.103.0/24")
    parser.add_argument("--networkid", type=int, default=100)
    parser.add_argument(
        "--action", choices=["start", "destroy", "apply"], default="start"
    )
    options = parser.parse_args()
    vfwobj = {
        "leases": [],
        "privatenetwork": options.privatenetwork,
        "tcpForwardRules": [],
        "id": options.networkid,
        "external": [
            {"ip": options.ip, "gateway": options.gateway, "vlan": options.vlan}
        ],
    }
    gw = Gateway(vfwobj)
    if options.action == "start":
        gw.start()
    elif options.action == "destroy":
        gw.destroy()
    elif options.action == "apply":
        gw.apply_firewall_rules()
