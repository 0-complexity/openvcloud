from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    machineId = int(args.getTag("machineId"))

    vmachine = db.cloudbroker.vmachine.get(machineId)
    cloudspace = db.cloudbroker.cloudspace.get(vmachine.cloudspaceId)
    accountId = cloudspace.accountId
    rescuedisks = db.cloudbroker.disk.search(
        {
            "gid": cloudspace.gid,
            "type": "C",
            "status": "CREATED",
            "accountId": {"$in": [None, accountId]},
        }
    )[1:]
    rescuedisks = [(disk["name"], disk["id"]) for disk in rescuedisks]

    popup = Popup(
        id="startmachine",
        header="Start Machine",
        submit_url="/restmachine/cloudbroker/machine/start",
        reload_on_success=False,
    )
    if rescuedisks:
        rescuedisks.insert(0, ("Normal boot", "null"))
        popup.addDropdown("Choose CD-ROM image", "diskId", rescuedisks)
    popup.addText("Reason", "reason")
    popup.addHiddenField("machineId", machineId)
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
