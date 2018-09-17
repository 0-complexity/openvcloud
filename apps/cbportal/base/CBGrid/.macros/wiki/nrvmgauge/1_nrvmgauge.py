def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    doc = args.doc
    id = args.getTag("id")
    gid = args.getTag("gid")
    width = args.getTag("width")
    height = args.getTag("height")
    result = "{{jgauge width:%(width)s id:%(id)s height:%(height)s val:%(running)s start:0 end:%(total)s}}"
    query = {"status": "RUNNING"}
    if gid:
        stacks = [
            stack["id"] for stack in db.cloudbroker.stack.search({"gid": int(gid)})[1:]
        ]
        query["stackId"] = {"$in": stacks}
    total = db.cloudbroker.vmachine.count({"status": {"$ne": "DESTROYED"}})
    running = db.cloudbroker.vmachine.count(query)
    result = result % {
        "height": height,
        "width": width,
        "running": running,
        "id": id,
        "total": total,
    }
    params.result = (result, doc)
    return params


def match(j, args, params, tags, tasklet):
    return True
