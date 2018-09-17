from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db, resourcestatus

    params.result = page = args.page
    diskId = args.getTag("diskId")
    cl = db.cloudbroker
    disk = cl.disk.get(int(diskId))
    cloudspace_ids = cl.cloudspace.search(
        {"$fields": ["id"], "$query": {"accountId": disk.accountId}}
    )[1:]
    machines = cl.vmachine.search({"cloudspaceId": {"$nin": cloudspace_ids}})[1:]
    machines_dropdown = []
    for machine in machines:
        name = "{}({})".format(machine["name"], machine["id"])
        machines_dropdown.append((name, machine["id"]))

    popup = Popup(
        id="attach_disk",
        header="Attach Disk",
        submit_url="/restmachine/cloudapi/machines/attachDisk",
    )
    popup.addDropdown("Choose Machine to attach to", "machineId", machines_dropdown)
    popup.addHiddenField("diskId", disk.id)
    popup.write_html(page)
    return params


def match(j, args, params, tags, tasklet):
    return True
