from JumpScale import j

descr = """
Creates gateway
"""

category = "vfw"
organization = "jumpscale"
author = "deboeckj@gig.tech"
license = "bsd"
version = "1.0"
roles = []
queue = "default"


def action(vfw):
    from CloudscalerLibcloud.gateway import Gateway

    gateway = Gateway(vfw)
    gateway.start()
