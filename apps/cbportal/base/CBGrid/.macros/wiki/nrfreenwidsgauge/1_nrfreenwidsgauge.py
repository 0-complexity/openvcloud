def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    doc = args.doc
    id = args.getTag("id")
    gid = int(args.getTag("gid"))
    width = args.getTag("width")
    height = args.getTag("height")
    result = "{{jgauge width:%(width)s id:%(id)s height:%(height)s val:%(running)s start:0 end:%(total)s}}"
    ac = db.libvirt.networkids
    if ac.exists(gid):
        networkids = ac.get(gid).networkids
    else:
        networkids = []
    allnetworkids = list()
    [allnetworkids.extend(network["networkids"] for network in ac.search({})[1:])]
    total = len(allnetworkids)
    running = len(networkids)
    if running < 10:
        result += "\n{color:red}** *LESS THAN 10 FREE NETWORK IDs*{color}"
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
