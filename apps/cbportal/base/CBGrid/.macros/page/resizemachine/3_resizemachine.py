from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    machineId = int(args.getTag("machineId"))

    vmachine = db.cloudbroker.vmachine.get(machineId)
    image = db.cloudbroker.image.get(vmachine.imageId)
    bootdisks = db.cloudbroker.disk.search(
        {"id": {"$in": vmachine.disks}, "type": "B"}
    )[1:]
    if len(bootdisks) != 1:
        return params
    popup = Popup(
        id="resizemachine",
        header="Resize Machine",
        submit_url="/restmachine/cloudbroker/machine/resize",
        showresponse=True,
    )
    if not image.hotResize:
        popup.addMessage("Machine resizing will take effect on next start")
    popup.addNumber("Number of VCPUS", "vcpus")
    popup.addNumber("Amount of memory", "memory")
    popup.addHiddenField("machineId", machineId)
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
