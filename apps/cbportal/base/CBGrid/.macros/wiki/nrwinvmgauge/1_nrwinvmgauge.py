def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    doc = args.doc
    id = args.getTag("id")
    gid = args.getTag("gid")
    width = args.getTag("width")
    height = args.getTag("height")
    result = "{{jgauge width:%(width)s id:%(id)s height:%(height)s val:%(running)s start:0 end:%(total)s}}"
    images = [x["id"] for x in db.cloudbroker.image.search({"type": "Windows"})[1:]]
    query = {"status": "RUNNING", "imageId": {"$in": images}}
    if gid:
        stacks = [stack["id"] for stack in db.cloudbroker.stack.search({"gid": int(gid)})[1:]]
        query["stackId"] = {"$in": stacks}
    active = db.cloudbroker.vmachine.count(query)
    total = db.cloudbroker.vmachine.count({"status": {"$ne": "DESTROYED"}})
    result = result % {
        "height": height,
        "width": width,
        "running": active,
        "id": id,
        "total": total,
    }
    params.result = (result, doc)
    return params


def match(j, args, params, tags, tasklet):
    return True
