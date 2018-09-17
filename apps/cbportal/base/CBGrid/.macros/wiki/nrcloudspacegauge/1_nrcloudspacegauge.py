def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    doc = args.doc
    id = args.getTag("id")
    gid = args.getTag("gid")
    width = args.getTag("width")
    height = args.getTag("height")
    result = "{{jgauge width:%(width)s id:%(id)s height:%(height)s val:%(running)s start:0 end:%(total)s}}"
    query = {"status": {"$ne": "DESTROYED"}}
    if gid:
        query["gid"] = int(gid)
    total = db.cloudbroker.account.count()
    running = db.cloudbroker.account.count(query)
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
