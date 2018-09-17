from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    params.result = page = args.page
    locations = list()
    for location in db.cloudbroker.location.search({})[1:]:
        locations.append((location["name"], location["gid"]))

    popup = Popup(
        id="createimage",
        header="Create Image",
        submit_url="/restmachine/cloudbroker/image/createImage",
        reload_on_success=False,
    )
    popup.addText("Name", "name", required=True)
    popup.addText("URL of image to import", "url", required=True)
    popup.addDropdown("Choose Location", "gid", locations)
    imagetypes = [("Linux", "Linux"), ("Windows", "Windows"), ("Other", "Other")]
    boottype = [("BIOS", "bios"), ("UEFI", "uefi")]
    hotResize = [("Yes", True), ("No", False)]
    popup.addDropdown("Choose Type", "imagetype", imagetypes)
    popup.addDropdown("Boot Type", "boottype", boottype)
    popup.addDropdown("Hot Resize", "hotresize", hotResize)
    popup.addText(
        "Username for the image leave empty when the image is cloud-init enabled",
        "username",
    )
    popup.addText(
        "Password for the image leave empty when the image is cloud-init enabled",
        "password",
    )
    popup.addText(
        "AccountId optional if you want to make the image for this account only",
        "accountId",
    )
    popup.write_html(page)
    return params


def match(j, args, params, tags, tasklet):
    return True
