from JumpScale import j

descr = """
Libvirt script to ge the domain
"""

name = "attach_device"
category = "libvirt"
organization = "cloudscalers"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
roles = []
async = True


def action(xml, machineid):
    import libvirt
    from CloudscalerLibcloud.utils.libvirtutil import LibvirtUtil
    connection = LibvirtUtil()
    domain = connection.connection.lookupByUUIDString(machineid)
    flags = libvirt.VIR_DOMAIN_DEVICE_MODIFY_CONFIG
    if domain.state()[0] in (libvirt.VIR_DOMAIN_RUNNING, libvirt.VIR_DOMAIN_PAUSED):
        flags |= libvirt.VIR_DOMAIN_DEVICE_MODIFY_LIVE
    domain.attachDeviceFlags(xml, flags)
    return domain.XMLDesc()



