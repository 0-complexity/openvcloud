from JumpScale import j

descr = """
Checks status
"""

name = "vfs_checkstatus"
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
    return gateway.is_running()
