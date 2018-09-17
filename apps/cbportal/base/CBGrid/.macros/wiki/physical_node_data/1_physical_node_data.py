def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    nid = args.requestContext.params.get("id")
    gid = args.requestContext.params.get("gid")
    node = db.system.node.searchOne({"id": int(nid) if nid else None})
    data = {"node": None, "stack": None, "ovs": None, "eco": None}

    # check node exists
    if not node:
        data["eco"] = "Node not found"
        args.doc.applyTemplate(data, False)
        return params
    data["node"] = node

    def get_interface_ip(interface):
        for netaddr in node["netaddr"]:
            if netaddr["name"] == interface:
                for ip in netaddr["ip"]:
                    return ip

    for interface in ["storage", "backplane1"]:
        storageip = get_interface_ip(interface)
        if storageip:
            break
    else:
        data["eco"] = "Could not find storage IP"
        args.doc.applyTemplate(data, False)
        return params

    data["storageip"] = storageip

    # get stack data if stack exists and is cpunode
    if "cpunode" in node["roles"]:
        stack = db.cloudbroker.stack.searchOne({"referenceId": nid})
        if not stack:
            data["eco"] = "Stack Id not Found"
            args.doc.applyTemplate(data, False)
            return params
        data["stack"] = stack

    if "storagedriver" in node["roles"]:
        acl = j.clients.agentcontroller.get()
        output = acl.executeJumpscript(
            "greenitglobe",
            "cloudbroker_get_storagenode",
            nid=nid,
            gid=gid,
            wait=True,
            args={"interface": interface},
        )
        if output["errorreport"] or output["state"] == "ERROR":
            data["ovsjob"] = output["guid"]
        else:
            data["ovs"] = output["result"]

    args.doc.applyTemplate(data)
    return params


def match(j, args, params, tags, tasklet):
    return True
