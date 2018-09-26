from JumpScale import j

descr = """
Applies the rules in the passed fwobject
"""

name = "vfs_applyconfig"
category = "vfw"
organization = "jumpscale"
author = "deboeckj@gig.tech"
license = "bsd"
version = "1.0"
roles = []
queue = "default"


def action(fwobject):
    from CloudscalerLibcloud.gateway import Gateway

    gateway = Gateway(fwobject)
    gateway.apply_firewall_rules()
    gateway.update_leases()
    gateway.update_proxies()
    gateway.update_cloud_init()
    return True
