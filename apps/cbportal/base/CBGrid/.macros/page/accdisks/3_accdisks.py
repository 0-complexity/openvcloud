def main(j, args, params, tags, tasklet):
    from cloudbrokerlib import resourcestatus
    from cloudbrokerlib.cloudbroker import db
    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)
    dtypes = db.cloudbroker.disktype.search({"$fields": ['id', 'description']})[1:]
    disktypemap = {dtype['id']: dtype['description'] for dtype in dtypes}    
        
    def disk_size(row, field):
        return "{} Gib".format(row[field])

    def disk_type(row, field):
        return disktypemap[row[field]]

    accountId = args.getTag("accountId")
    filters = {
        "status": resourcestatus.Disk.CREATED,
        "accountId": int(accountId),
        "type": {"$ne": "C"},
    }

    fields = [
        {"name": "Name", "value": "[%(name)s|/CBGrid/Disk?id=%(id)s]", "id": "name"},
        {"name": "Size", "value": disk_size, "id": "sizeMax"},
        {"name": "Type", "value": disk_type, "id": "type"},
        {"name": "Path", "value": "referenceId", "id": "referenceId"},
    ]
    tableid = modifier.addTableFromModel(
        "cloudbroker", "disk", fields, filters, selectable="rows"
    )
    modifier.addSearchOptions("#%s" % tableid)
    modifier.addSorting("#%s" % tableid, 1, "desc")

    params.result = page

    return params


def match(j, args, params, tags, tasklet):
    return True
