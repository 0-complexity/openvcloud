from JumpScale import j

descr = """
Will set the `url` and `lastModified` fields with default values
Will migrate models of vfw
"""

category = "libvirt"
organization = "greenitglobe"
author = "ali.chaddad@gig.tech"
license = "bsd"
version = "2.0"
roles = ["master"]
async = True


def action():
    ccl = j.clients.osis.getNamespace("cloudbroker")
    vcl = j.clients.osis.getNamespace("vfw")
    ccl.image.updateSearch({"url": None}, {"$set": {"url": "", "lastModified": 0}})
    for vfw in vcl.virtualfirewall.search({}, size=0)[1:]:
        if "external" not in vfw:
            cloudspace = ccl.cloudspace.get(int(vfw["domain"]))
            extnetwork = ccl.externalnetwork.get(cloudspace.externalnetworkId)
            vfw.pop("ips", None)
            external = {
                "vlan": vfw.pop("vlan"),
                "ips": [cloudspace.externalnetworkip],
                "gateway": extnetwork.gateway,
            }
            vcl.virtualfirewall.updateSearch(
                {"guid": vfw["guid"]},
                {"$set": {"external": external}, "$unset": {"pubips": "", "vlan": ""}},
            )


if __name__ == "__main__":
    action()
