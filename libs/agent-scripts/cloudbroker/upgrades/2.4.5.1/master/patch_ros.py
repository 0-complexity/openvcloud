from JumpScale import j

descr = """
Upgrade script
Patch ROS.
"""

category = "libvirt"
organization = "greenitglobe"
author = "ali.chaddad@gig.tech"
license = "bsd"
version = "2.0"
roles = ["master"]
async = True


def action():
    acl = j.clients.agentcontroller.get()
    vcl = j.clients.osis.getNamespace("vfw")
    vfws = vcl.virtualfirewall.search({}, size=0)[1:]

    args = dict()
    args["script"] = "/ip socks set enabled=no"
    for vfw in vfws:
        args["fwobject"] = vfw
        try:
            acl.executeJumpscript(
                "jumpscale",
                "vfs_runscript_routeros",
                args=args,
                nid=vfw["nid"],
                gid=vfw["gid"],
                timeout=5,
            )
        except:
            j.errorconditionhandler.raiseOperationalWarning(
                "Can't connect to routeros {}".format(vfw["guid"])
            )


if __name__ == "__main__":
    action()
