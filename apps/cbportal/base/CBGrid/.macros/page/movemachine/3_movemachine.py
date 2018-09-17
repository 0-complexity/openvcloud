from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    machineId = int(args.getTag("machineId"))

    vmachine = db.cloudbroker.vmachine.get(machineId)
    cloudspace = db.cloudbroker.cloudspace.get(vmachine.cloudspaceId)
    stacks = db.cloudbroker.stack.search(
        {"status": "ENABLED", "gid": cloudspace.gid, "images": vmachine.imageId}
    )[1:]
    cpu_nodes = [
        (stack["name"], stack["id"])
        for stack in stacks
        if vmachine.stackId != stack["id"]
    ]

    popup = Popup(
        id="movemachine",
        header="Move machine to another CPU node",
        submit_url="/restmachine/cloudbroker/machine/moveToDifferentComputeNode",
        reload_on_success=False,
    )
    popup.addDropdown("Target CPU Node", "targetStackId", cpu_nodes, required=True)
    popup.addDropdown(
        "Force (might require VM to restart)",
        "force",
        (("No", "false"), ("Yes", "true")),
        required=True,
    )
    popup.addText("Reason", "reason", required=True)
    popup.addHiddenField("machineId", machineId)
    popup.addHiddenField("async", "true")
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
