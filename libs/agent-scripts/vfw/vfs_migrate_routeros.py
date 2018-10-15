from JumpScale import j

descr = """
move vfw
"""

organization = "jumpscale"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
category = "deploy.routeros"
period = 0  # always in sec
enable = True
async = True
queue = "hypervisor"


def action(networkid, sourceip, vlan, externalip):
    from CloudscalerLibcloud.utils.network import Network, NetworkTool
    import libvirt
    import netaddr
    from xml.etree import ElementTree
    import re

    target_con = libvirt.open()
    try:
        source_con = libvirt.open("qemu+ssh://%s/system" % sourceip)
    except:
        source_con = None
    network = Network()
    config = j.core.config.get("routeros", "main")
    netrange = config["netrange_internal"]
    internalip = str(
        netaddr.IPAddress(netaddr.IPNetwork(netrange).first + int(networkid))
    )

    netinfo = [{"type": "vlan", "id": vlan}, {"type": "vxlan", "id": networkid}]
    extbridge = j.system.ovsnetconfig.getVlanBridge(vlan)
    name = "routeros_%04x" % networkid

    with NetworkTool(netinfo):
        if source_con:
            templatepath = "/var/lib/libvirt/images/routeros/template/routeros.qcow2"
            destination = "/var/lib/libvirt/images/routeros/{0:04x}".format(networkid)
            destinationfile = j.system.fs.joinPaths(destination, "routeros.qcow2")
            try:
                domain = source_con.lookupByName(name)
            except libvirt.libvirtError:
                domain = None
            if domain:
                if domain.state()[0] == libvirt.VIR_DOMAIN_RUNNING:
                    localip = j.system.net.getReachableIpAddress(sourceip, 22)
                    targeturl = "tcp://{}".format(localip)
                    if not j.system.fs.exists(destination):
                        j.system.fs.createDir(destination)
                    if not j.system.fs.exists(destinationfile):
                        j.system.fs.copyFile(templatepath, destinationfile)
                    xmldom = ElementTree.fromstring(domain.XMLDesc())
                    seclabel = xmldom.find("seclabel")
                    if seclabel is not None:
                        xmldom.remove(seclabel)
                    xml = ElementTree.tostring(xmldom)
                    xml = re.sub(
                        r"bridge='(public|ext-\w+)'",
                        r"bridge='{}'".format(extbridge),
                        xml,
                    )
                    flags = (
                        libvirt.VIR_MIGRATE_LIVE
                        | libvirt.VIR_MIGRATE_PERSIST_DEST
                        | libvirt.VIR_MIGRATE_UNDEFINE_SOURCE
                        | libvirt.VIR_MIGRATE_NON_SHARED_DISK
                    )
                    try:
                        domain.migrate2(
                            target_con, flags=flags, dxml=xml, uri=targeturl
                        )
                    except Exception as e:
                        try:
                            target_domain = target_con.lookupByName(name)
                            target_domain.undefine()
                        except:
                            pass  # vm wasn't created on target
                        raise e
                    domain = target_con.lookupByName(name)
                    network.protect_external(domain, externalip)
                    network.protect_gwmgmt(domain, internalip)
                    return domain.XMLDesc()
                else:
                    domain.undefine()
                    return False
            else:
                return False
        else:
            # source is not available caller should probable do a restore from scratch
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--networkid", type=int)
    parser.add_argument("-s", "--sourceip")
    parser.add_argument("-v", "--vlan", type=int, default=0)
    options = parser.parse_args()
    action(options.networkid, options.sourceip, options.vlan)
