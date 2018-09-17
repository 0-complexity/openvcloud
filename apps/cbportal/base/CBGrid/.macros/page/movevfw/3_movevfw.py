from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    cloudspaceId = args.getTag("cloudspaceId")
    cloudspace = db.cloudbroker.cloudspace.get(int(cloudspaceId))

    if cloudspace.status != "DEPLOYED":
        popup = Popup(id="movevfw", header="CloudSpace is not deployed", submit_url="#")
        popup.write_html(page)
        return params

    popup = Popup(
        id="movevfw",
        header="Move Virtual Firewall",
        submit_url="/restmachine/cloudbroker/cloudspace/moveVirtualFirewallToFirewallNode",
        reload_on_success=False,
    )

    key = "%(gid)s_%(networkId)s" % cloudspace.dump()
    if not db.vfw.virtualfirewall.exists(key):
        popup = Popup(
            id="movevfw", header="CloudSpace is not properly deployed", submit_url="#"
        )
        popup.write_html(page)
        return params

    vfw = db.vfw.virtualfirewall.get(key)
    query = {
        "status": "ENABLED",
        "gid": cloudspace.gid,
        "referenceId": {"$ne": str(vfw.nid)},
    }
    vfwnodes = db.cloudbroker.stack.search(query)[1:]
    if not vfwnodes:
        popup = Popup(
            id="movevfw", header="No other Firewall node available", submit_url="#"
        )
        popup.write_html(page)
        return params

    dropnodes = [("Choose Automaticly", "null")]
    for stack in vfwnodes:
        dropnodes.append(("FW Node %(name)s" % stack, stack["referenceId"]))

    popup.addDropdown("FW Node to move to", "targetNid", dropnodes)
    popup.addHiddenField("cloudspaceId", cloudspaceId)
    popup.addHiddenField("async", "true")

    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
