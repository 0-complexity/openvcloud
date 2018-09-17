from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    params.result = page = args.page

    locations = [(loc["name"], loc["gid"]) for loc in db.cloudbroker.location.search({})[1:]]
    popup = Popup(
        id="addpublicnetwork",
        header="Add Public Network",
        submit_url="/restmachine/cloudbroker/iaas/addPublicNetwork",
    )
    popup.addDropdown("Choose Location", "gid", locations)
    popup.addText("Network", "network", required=True, placeholder="8.8.8.0/24")
    popup.addText("Gateway", "gateway", required=True, placeholder="8.8.8.1")
    popup.addText(
        "First Free Public IP Address", "startip", required=True, placeholder="8.8.8.2"
    )
    popup.addText(
        "Last Free Public IP Address", "endip", required=True, placeholder="8.8.8.254"
    )
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
