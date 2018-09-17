def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)

    stackid = args.getTag("stackid")
    filters = {"status": {"$nin": ["DESTROYED", "DELETED"]}}
    if stackid:
        stackid = int(stackid)
        stack = db.cloudbroker.stack.get(stackid)
        images = db.cloudbroker.image.search({"id": {"$in": stack.images}})[1:]
        imageids = [image["id"] for image in images]
        filters["id"] = {"$in": imageids}

    locations = db.cloudbroker.location.search(
        {"$query": {}, "$fields": ["gid", "name"]}
    )[1:]
    locationmap = {loc["gid"]: loc["name"] for loc in locations}

    def getLocation(field, row):
        gid = field[row]
        if not gid:
            return ""
        name = locationmap[gid]
        return "[{name} ({gid})|/cbgrid/grid?gid={gid}]".format(gid=gid, name=name)

    fields = [
        {
            "name": "Name",
            "id": "name",
            "value": "<a href='/cbgrid/image?id=%(id)s'>%(name)s</a>",
        },
        {"name": "Location", "id": "gid", "filterable": False, "value": getLocation},
        {"name": "Status", "id": "status", "value": "status"},
        {"name": "Size", "id": "size", "type": "int", "value": "%(size)s GiB"},
    ]
    tableid = modifier.addTableFromModel("cloudbroker", "image", fields, filters)
    modifier.addSearchOptions("#%s" % tableid)

    params.result = page
    return params


def match(j, args, params, tags, tasklet):
    return True
