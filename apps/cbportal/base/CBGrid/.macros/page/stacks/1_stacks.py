def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import CloudBroker, db

    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)

    imageid = args.getTag("imageid")
    filters = dict()
    grids = dict()
    cb = CloudBroker()
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
            grid = cb.syscl.grid.get(gid)
            grids[gid] = grid
        return grids[gid]

    def fill_stack(stack):
        if "usedros" not in stack:
            grid = get_grid(stack)
            cb.getStackCapacity(stack, grid, nodesbyid)

    def get_vms(stack, column):
        fill_stack(stack)
        return "{} + {}".format(stack["usedros"], stack["usedvms"])

    def get_memory(stack, column):
        fill_stack(stack)
        meminfo = "{:.2f} + {} / {:.2f} GiB".format(
            stack["usedmemory"] / 1024.,
            stack["reservedmemory"] / 1024,
            stack["totalmemory"] / 1024.,
        )
        return meminfo

    fields = [
        {
            "name": "ID",
            "id": "id",
            "value": "<a href='/cbgrid/Stack?id=%(id)s'>%(id)s</a>",
        },
        {
            "name": "Grid ID",
            "id": "gid",
            "value": "<a href='/cbgrid/grid?gid=%(gid)s'>%(gid)s</a>",
        },
        {"name": "Name", "id": "name", "value": "name", "type": "text"},
        {"name": "Status", "id": "status", "value": "status"},
        {
            "name": "Reference ID",
            "id": "referenceId",
            "value": "<a href='/grid/grid node?id=%(referenceId)s&gid=%(gid)s'>%(referenceId)s</a>",
            "type": "text",
        },
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
        "cloudbroker", "stack", fields, filters, selectable="rows"
    )
    modifier.addSearchOptions("#%s" % tableid)

    params.result = page
    return params


def match(j, args, params, tags, tasklet):
    return True
