from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    disk_types = [("Data disk", "D"), ("Boot disk", "B")]
    accountId = args.getTag("accountId")
    locations = list()
    for location in db.cloudbroker.location.search({})[1:]:
        locations.append((location["name"], location["gid"]))

    popup = Popup(
        id="create_disk",
        header="Create Disk",
        submit_url="/restmachine/cloudapi/disks/create",
    )
    popup.addText("Name", "name", required=True)
    popup.addText("Description", "description", required=True)
    popup.addDropdown("Choose Location", "gid", locations)
    popup.addText("Disk size", "size", type="number", placeholder="Optional, default to 10 GB")
    popup.addDropdown("Choose Disk type", "type", disk_types)
    popup.addText("Total iops per sec", "iops", type="number", placeholder="Optional, default to 2000")
    popup.addHiddenField("accountId", accountId)
    popup.write_html(page)
    return params

def match(j, args, params, tags, tasklet):
    return True
