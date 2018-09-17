def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db, CloudBroker

    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)
    cb = CloudBroker()

    imageid = args.getTag("imageid")
    filters = dict(roles={"$in": ["cpunode", "storagenode"]})
    grids = dict()
    query = {"$fields": ["id", "memory"]}
    nodesbyid = {
        node["id"]: node["memory"]
        for node in db.system.node.search(query)[1:]
        if "memory" in node
    }

    if imageid:
        args.tags.tags.pop("imageid")
        try:
            filters["images"] = int(imageid)
        except ValueError:
            pass

    for tag, val in args.tags.tags.iteritems():
        val = args.getTag(tag)
        if val:
            filters[tag] = (
                j.basetype.integer.fromString(val)
                if j.basetype.integer.checkString(val)
                else val
            )

    def get_grid(stack):
        gid = stack["gid"]
        if gid not in grids:
            grid = db.system.grid.get(gid)
            grids[gid] = grid
        return grids[gid]

    def fill_stack(stack):
        if "usedros" not in stack:
            grid = get_grid(stack)
            cb.getStackCapacity(stack, grid, nodesbyid)

    def get_vms(node, column):
        stack = db.cloudbroker.stack.searchOne({"referenceId": str(node["id"])})
        if stack:
            fill_stack(stack)
            return "{} + {}".format(stack["usedros"], stack["usedvms"])
        else:
            return ""

    def get_memory(node, column):
        stack = cb.cbcl.stack.searchOne({"referenceId": str(node["id"])})
        if stack:
            fill_stack(stack)
            meminfo = "{:.2f} + {} / {:.2f} GiB".format(
                stack["usedmemory"] / 1024.,
                stack["reservedmemory"] / 1024,
                stack["totalmemory"] / 1024.,
            )
            return meminfo
        else:
            return "%s GiB" % (node["memory"] / 1024)

    fields = [
        {
            "name": "ID",
            "id": "id",
            "value": "<a href='/cbgrid/physicalNode?id=%(id)s&gid=%(gid)s'>%(id)s</a>",
        },
        {
            "name": "Grid ID",
            "id": "gid",
            "value": "<a href='/cbgrid/grid?gid=%(gid)s'>%(gid)s</a>",
        },
        {"name": "Name", "id": "name", "value": "name", "type": "text"},
        {"name": "Status", "id": "status", "value": "status"},
        {"name": "Roles", "id": "roles", "value": "roles"},
        {
            "name": "ROS + VMS",
            "id": "is",
            "sortable": False,
            "filterable": False,
            "value": get_vms,
        },
        {
            "name": "Memory",
            "id": "id",
            "value": get_memory,
            "filterable": False,
            "sortable": False,
        },
    ]
    tableid = modifier.addTableFromModel(
        "system", "node", fields, filters, selectable="rows"
    )
    modifier.addSearchOptions("#%s" % tableid)

    params.result = page
    return params


def match(j, args, params, tags, tasklet):
    return True
