from JumpScale import j
from CloudscalerLibcloud.utils import libvirtutil
from . import rules
import netaddr


class Network(object):
    def __init__(self, libvirtcon=None):
        if libvirtcon:
            self.libvirtutil = libvirtcon
        else:
            self.libvirtutil = libvirtutil.LibvirtUtil()

    def cleanup_flows(self, bridge, port, mac, ip=None):
        cmd = rules.CLEANUPFLOWS_CMD.format(mac=mac, port=port, bridge=bridge)
        j.system.process.execute(cmd, dieOnNonZeroExitCode=False)
        if ip:
            cmd = rules.CLEANUPFLOWS_CMD_IP.format(bridge=bridge, ipaddress=ip)
            j.system.process.execute(cmd, dieOnNonZeroExitCode=False)

    def close(self):
        self.libvirtutil.close()

    def get_external_interface(self, domain):
        for nic in self.libvirtutil.get_domain_nics_info(domain):
            if nic["bridge"].startswith("pub") or nic["bridge"].startswith("ext"):
                return nic["name"], nic["mac"], nic["bridge"]
        raise LookupError("Could not find public interface")

    def get_gwmgmt_interface(self, domain):
        for nic in self.libvirtutil.get_domain_nics_info(domain):
            if nic["bridge"] == "gw_mgmt":
                return nic["name"], nic["mac"]

    def get_port(self, interface):
        portcmd = "ovs-vsctl -f table -d bare --no-heading -- --columns=ofport list Interface {}".format(
            interface
        )
        exitcode, port = j.system.process.execute(portcmd, dieOnNonZeroExitCode=False)
        return port.strip()

    def cleanup_external(self, domain):
        try:
            interface, mac, bridge = self.get_external_interface(domain)
        except LookupError:
            return
        port = self.get_port(interface)
        if port:
            self.cleanup_flows(bridge, port, mac)

    def protect_external(self, domain, ipaddress):
        try:
            interface, mac, bridge = self.get_external_interface(domain)
        except LookupError:
            return
        return self.protect_external_bridge(bridge, interface, mac, ipaddress)

    def protect_external_bridge(self, bridge, interface, mac, ipaddress):
        ipaddress = str(netaddr.IPNetwork(ipaddress).ip)
        port = self.get_port(interface)
        self.cleanup_flows(bridge, port, mac, ipaddress)
        tmpfile = j.system.fs.getTmpFilePath()
        try:
            j.system.fs.writeFile(
                tmpfile,
                rules.PUBLICINPUT.format(port=port, mac=mac, publicipv4addr=ipaddress),
            )
            j.system.process.execute(
                "ovs-ofctl add-flows {bridge} {file}".format(
                    file=tmpfile, bridge=bridge
                )
            )
        finally:
            j.system.fs.remove(tmpfile)

    def protect_gwmgmt(self, domain, ipaddress):
        interface, mac = self.get_gwmgmt_interface(domain)
        port = self.get_port(interface)
        self.cleanup_flows("gw_mgmt", port, mac, ipaddress)
        tmpfile = j.system.fs.getTmpFilePath()
        try:
            j.system.fs.writeFile(
                tmpfile,
                rules.GWMGMTINPUT.format(port=port, mac=mac, ipaddress=ipaddress),
            )
            j.system.process.execute(
                "ovs-ofctl add-flows {bridge} {file}".format(
                    file=tmpfile, bridge="gw_mgmt"
                )
            )
        finally:
            j.system.fs.remove(tmpfile)

    def cleanup_gwmgmt(self, domain):
        interface, mac = self.get_gwmgmt_interface(domain)
        port = self.get_port(interface)
        if port:
            self.cleanup_flows("gw_mgmt", port, mac)


class NetworkTool:
    def __init__(self, netinfo, connection=None):
        self.netinfo = netinfo
        if connection is None:
            self.connection = libvirtutil.LibvirtUtil()
        else:
            self.connection = connection
        self.locks = []

    def __enter__(self):
        for net in self.netinfo:
            if net["type"] == "vlan":
                bridgename = j.system.ovsnetconfig.getVlanBridge(net["id"])
                lockname = "vlan_{}".format(bridgename)
                self.locks.append(lockname)
                j.system.fs.lock(lockname)
                self._create_vlan(bridgename, net["id"])
            elif net["type"] == "vxlan":
                lockname = "vxlan_{}".format(net["id"])
                self.locks.append(lockname)
                j.system.fs.lock(lockname)
                self._create_vxlan(net["id"])
        return self

    def _create_vxlan(self, networkid):
        vxnet = j.system.ovsnetconfig.ensureVXNet(networkid, "vxbackend")
        networks = self.connection.connection.listNetworks()
        bridgename = vxnet.bridge.name
        if bridgename not in networks:
            self.connection.createNetwork(bridgename, bridgename)

    def _create_vlan(self, bridgename, networkid):
        nics = j.system.net.getNics()
        if bridgename not in nics:
            extbridge = "ext-bridge"
            if extbridge not in nics:
                extbridge = "backplane1"
            j.system.ovsnetconfig.newVlanBridge(bridgename, extbridge, networkid)
        if not self.connection.checkNetwork(bridgename):
            self.connection.createNetwork(bridgename, bridgename)

    def __exit__(self, *args):
        for lock in self.locks:
            j.system.fs.unlock(lock)
