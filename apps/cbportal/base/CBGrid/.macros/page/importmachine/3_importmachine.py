from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    cloudspaceId = int(args.getTag("cloudspaceId"))

    cloudspace = db.cloudbroker.cloudspace.get(cloudspaceId)
    stacks = db.cloudbroker.stack.search({"gid": cloudspace.gid, "status": "ENABLED"})[
        1:
    ]

    dropstacks = list()

    def sizeSorter(size):
        return size["memory"]

    def sortName(item):
        return item["name"]

    for stack in sorted(stacks, key=sortName):
        dropstacks.append((stack["name"], stack["id"]))

    popup = Popup(
        id="importmachine",
        header="Import Machine",
        submit_url="/restmachine/cloudapi/machines/importOVF",
        reload_on_success=False,
    )
    popup.addText("Machine Name", "name", required=True)
    popup.addText("Machine Description", "desc", required=True)
    popup.addText("Import Link", "link", required=True)
    popup.addText("OVF path", "path")
    popup.addText("Username for Link", "username")
    popup.addText("Password for Link", "passwd", type="password")
    popup.addNumber("Number of VCPUS", "vcpus")
    popup.addNumber("Amount of memory", "memory")
    popup.addHiddenField("cloudspaceId", cloudspaceId)
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
