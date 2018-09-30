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


if __name__ == "__main__":
    vfw = {
        "_ckey": "",
        "_meta": ["osismodel", "vfw", "virtualfirewall", 1],
        "accesstime": 1537790629,
        "deployment_jobguid": "37de9510f1c64b90b236dacb0e3b825c",
        "descr": "",
        "domain": "35",
        "external": {
            "gateway": "172.17.0.1",
            "guid": "",
            "ips": ["172.17.1.120/16"],
            "vlan": 0,
        },
        "gid": 66,
        "guid": "66_235",
        "host": "10.199.0.235",
        "id": 235,
        "internalip": "",
        "masquerade": True,
        "moddate": 1538302293,
        "name": "",
        "networkid": "",
        "nid": 7,
        "password": "rooter",
        "privatenetwork": "192.168.103.0/24",
        "state": "STARTED",
        "tcpForwardRules": [],
        "type": "vgw",
        "username": "vscalers",
        "version": 0,
        "wsForwardRules": [],
    }
    action(vfw)

