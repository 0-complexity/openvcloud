from JumpScale.portal.docgenerator.popup import Popup
import yaml


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page

    gid = int(args.getTag("gid"))
    settings = ""
    grid_settings = db.system.grid.searchOne({"id": gid}).get("settings", {})
    if grid_settings:
        settings = yaml.safe_dump(grid_settings, default_flow_style=False)

    popup = Popup(
        id="settings",
        header="Change grid settings",
        submit_url="/restmachine/cloudbroker/grid/changeSettings",
    )
    popup.addTextArea(
        "Change the data to update grid settings",
        "settings",
        required=True,
        value=settings,
        rows=10,
    )
    popup.addHiddenField("id", gid)
    popup.write_html(page)
    return params
