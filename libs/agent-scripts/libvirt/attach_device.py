from JumpScale import j

descr = """
Libvirt script to ge the domain
"""

name = "attach_device"
category = "libvirt"
organization = "greenitglobe"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
roles = []
queue = "hypervisor"
async = True


def action(xml, machineid, ipcidr=None, vlan=None):
    import libvirt
    from CloudscalerLibcloud.utils.libvirtutil import LibvirtUtil
    from CloudscalerLibcloud.utils.network import Network, NetworkTool

    connection = LibvirtUtil()
    netinfo = []
    if vlan:
        netinfo.append({"id": vlan, "type": "vlan"})
    try:
        with NetworkTool(netinfo, connection):
            domain = connection.get_domain_obj(machineid)
            if domain is None:
                return
            flags = 0
            if domain.state()[0] in (
                libvirt.VIR_DOMAIN_RUNNING,
                libvirt.VIR_DOMAIN_PAUSED,
            ):
                flags |= libvirt.VIR_DOMAIN_DEVICE_MODIFY_LIVE
            if domain.isPersistent():
                flags |= libvirt.VIR_DOMAIN_DEVICE_MODIFY_CONFIG
            if flags != 0:
                try:
                    domain.attachDeviceFlags(xml, flags)
                except libvirt.libvirtError as e:
                    if e.get_error_code() == libvirt.VIR_ERR_CONFIG_UNSUPPORTED:
                        return False
                    raise

            if ipcidr:
                network = Network(connection)
                network.protect_external(domain, ipcidr)
            return domain.XMLDesc()
    finally:
        connection.close()
