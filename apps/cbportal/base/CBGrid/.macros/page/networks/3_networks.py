def main(j, args, params, tags, tasklet):
    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)

    filters = dict()
    for tag, val in args.tags.tags.iteritems():
        val = args.getTag(tag)
        if val and val.isdigit():
            val = int(val)
        filters[tag] = val

    def makeNS(row, field):
        return str(", ".join(row[field]['ips']))

    fields = [
        {"name": "GID", "id": "gid", "value": "[%(gid)s|/CBGrid/grid?gid=%(gid)s]"},
        {
            "name": "id",
            "id": "id",
            "value": "[%(id)s|/CBGrid/private network?id=%(id)s&gid=%(gid)s] (%(id)04x)",
        },
        {
            "name": "Cloud Space ID",
            "id": "domain",
            "value": "[%(domain)s|/CBGrid/cloud space?id=%(domain)s]",
        },
        {
            "name": "Network Type",
            "id": "type",
            "value": "type",
        },
        {"name": "Public IPs", "id": "external", "value": makeNS, "type": "text"},
        {"name": "Management IP", "id": "host", "value": "host", "type": "text"},
    ]
    tableid = modifier.addTableFromModel("vfw", "virtualfirewall", fields, filters)
    modifier.addSearchOptions("#%s" % tableid)
    modifier.addSorting("#%s" % tableid, 1, "desc")

    params.result = page

    return params


def match(j, args, params, tags, tasklet):
    return True
