def main(j, args, params, tags, tasklet):
    
    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)

    fields = [
        {"name": "ID", "value": "[%(id)s|/CBGrid/disk Type?id=%(id)s]", "id": "id"},
        {"name": "Description", "id": "description", "value": "description"},
        {"name": "VPool", "id": "vpool", "value": "vpool"},
        {"name": "Cache Ratio", "id": "cacheratio", "value": "cacheratio"},
        {"name": "Snapshotable", "id": "snapshotable", "value": "snapshotable"},
    ]
    tableid = modifier.addTableFromModel("cloudbroker", "disktype", fields, {}, selectable="rows")
    modifier.addSearchOptions("#%s" % tableid)

    params.result = page
    return params


def match(j, args, params, tags, tasklet):
    return True
