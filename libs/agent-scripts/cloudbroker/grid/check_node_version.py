from JumpScale import j
import yaml

descr = """
This script checks node version, if it out of date, trigger update_node jumpscript to update it.
"""
organization = "greenitglobe"
category = "cloudbroker"
version = "1.0"
period = "0 12 1/2 * *"  # every 2 days at 12:00
startatboot = True
enable = True
roles = ["node"]
queue = "process"
log = True


def action():
    nid = j.application.whoAmI.nid
    gid = j.application.whoAmI.gid

    if j.system.platformtype.isVirtual():
        return

    scl = j.clients.osis.getNamespace("system")
    node = scl.node.get(nid)
    if not scl.version.count({"status": "INSTALLING"}) and node.status == "ENABLED":
        current_version = j.application.config["system"]["version"]
        version = scl.version.searchOne({"status": "CURRENT"})["name"]
        if current_version != version:
            nodename = node.name.split(".")[0]
            args = {"nodename": nodename}
            acl = j.clients.agentcontroller.get()
            acl.executeJumpscript(
                "greenitglobe",
                "update_node",
                role="controller",
                gid=gid,
                args=args,
                wait=False,
            )


if __name__ == "__main__":
    action()
