def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    id = args.requestContext.params.get("id")
    gid = args.requestContext.params.get("gid")
    try:
        id = int(id)
        gid = int(gid)
    except:
        pass
    if not isinstance(gid, int) or not isinstance(id, int):
        args.doc.applyTemplate({})
        return params

    id = int(id)
    key = "%s_%s" % (gid, id)
    cloudspaces = db.cloudbroker.cloudspace.search({"gid": int(gid), "networkId": id})[
        1:
    ]
    data = {}
    if cloudspaces:
        data["cloudspaceId"] = cloudspaces[0]["id"]
        data["cloudspaceName"] = cloudspaces[0]["name"]

    if not db.vfw.virtualfirewall.exists(key):
        # check if cloudspace with id exists

        args.doc.applyTemplate(data)
        return params

    network = db.vfw.virtualfirewall.get(key)
    obj = network.dump()
    obj.update(data)
    if db.system.node.exists(obj["nid"]):
        obj["nodename"] = db.system.node.get(obj["nid"]).name
    else:
        obj["nodename"] = str(obj["nid"])
    try:
        obj["running"] = (
            "RUNNING"
            if j.apps.cloudbroker.iaas.cb.netmgr.fw_check(network.guid, timeout=5)
            else "HALTED"
        )
    except:
        obj["running"] = "UNKNOWN"

    args.doc.applyTemplate(obj, True)
    return params


def match(j, args, params, tags, tasklet):
    return True
