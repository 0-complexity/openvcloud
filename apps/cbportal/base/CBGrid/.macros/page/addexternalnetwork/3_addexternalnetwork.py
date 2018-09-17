from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    params.result = page = args.page
    locations = db.cloudbroker.location.search({})[1:]

    popup = Popup(
        id="addexternalnetwork",
        header="Add External Network",
        submit_url="/restmachine/cloudbroker/iaas/addExternalNetwork",
    )
    popup.addText("Name", "name", required=True)
    popup.addText("Subnet CIDR", "subnet", required=True)
    popup.addText("Gateway IP Address", "gateway", required=True)
    popup.addText("Start IP Address", "startip", required=True)
    popup.addText("End IP Address", "endip", required=True)
    popup.addNumber(
        "VLAN Tag (leave empty if its the standard public bridge)",
        "vlan",
        required=False,
    )
    popup.addNumber(
        "AccountId (make external network exclusive to this accountId otherwise leave empty)",
        "accountId",
        required=False,
    )
    popup.addDropdown(
        "Choose Location",
        "gid",
        [(location["name"], location["gid"]) for location in locations],
    )
    popup.addText(
        " Enter list of ips(seperated by commas), eg 8.8.8.8,10.10.10.10. If you want to disable the health check, enter 127.0.0.1",
        "pingips",
        placeholder="If left empty default will be 8.8.8.8",
    )
    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
