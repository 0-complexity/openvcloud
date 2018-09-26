from JumpScale import j

descr = """Deletes gateway"""

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
    gateway.destroy()
    return True
