from JumpScale import j

descr = """
Backup routeros if accesstime is less then 2hours
"""

organization = "jumpscale"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
category = "deploy.routeros"
enable = True
async = True
queue = "hypervisor"
roles = ["cpunode"]
period = 600


def action():
    import time

    vcl = j.clients.osis.getNamespace("vfw")
    scl = j.clients.osis.getNamespace("system")
    grid = scl.grid.get(j.application.whoAmI.gid)
    ovs_credentials = grid.settings.get("ovs_credentials", {})
    edgeuser = ovs_credentials.get("edgeuser")
    edgepassword = ovs_credentials.get("edgepassword")
    vfws = vcl.virtualfirewall.search(
        {
            "nid": j.application.whoAmI.nid,
            "accesstime": {"$gt": int(time.time()) - 7200},
            "type": "routeros"
        }, size=0
    )[1:]
    acl = j.clients.agentcontroller.get()
    edgeip, edgeport, edgetransport = acl.execute(
        "greenitglobe",
        "getedgeconnection",
        role="storagedriver",
        gid=j.application.whoAmI.gid,
    )
    for vfw in vfws:
        networkidHex = "%04x" % int(vfw["id"])
        sourcefile = "/var/lib/libvirt/images/routeros/{:04x}/routeros.qcow2".format(
            vfw["id"]
        )
        devicename = "routeros/{0}/routeros-small-{0}".format(networkidHex)
        destinationfile = "openvstorage+%s://%s:%s/%s" % (
            edgetransport,
            edgeip,
            edgeport,
            devicename,
        )
        print("Backing up {} to {}".format(sourcefile, destinationfile))
        destination = destinationfile.replace("://", ":")
        if edgeuser:
            destination += ":username={}:password={}".format(edgeuser, edgepassword)
        try:
            j.system.platform.qemu_img.info(destination)
            create = False
        except:
            create = True
        j.system.platform.qemu_img.convert(
            sourcefile, "qcow2", destination, "raw", createTarget=create
        )


if __name__ == "__main__":
    action()
