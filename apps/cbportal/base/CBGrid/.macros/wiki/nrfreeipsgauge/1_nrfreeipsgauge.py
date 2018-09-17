def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    doc = args.doc
    id = args.getTag("id")
    gid = args.getTag("gid")
    width = args.getTag("width")
    height = args.getTag("height")
    result = "{{jgauge width:%(width)s id:%(id)s height:%(height)s val:%(running)s start:0 end:%(total)s}}"
    query = {}
    if gid:
        query["gid"] = int(gid)
    freeips = list()
    [
        freeips.extend(externalnetwork["ips"])
        for externalnetwork in db.cloudbroker.externalnetwork.search({})[1:]
    ]
    total = len(freeips) + db.cloudbroker.cloudspace.count({"status": "DEPLOYED"})
    if total < 10:
        result += "\n{color:red}** *LESS THAN 10 FREE IPs*{color}"
    result = result % {
        "height": height,
        "width": width,
        "running": len(freeips),
        "id": id,
        "total": total,
    }
    params.result = (result, doc)
    return params


def match(j, args, params, tags, tasklet):
    return True
