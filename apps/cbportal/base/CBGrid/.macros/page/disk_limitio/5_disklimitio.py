from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = page = args.page
    diskid = args.getTag("diskid")
    disk = db.cloudbroker.disk.get(int(diskid))
    iotune = disk.iotune

    popup = Popup(
        id="disk_limitio_%s" % disk.id,
        header="Limit disk io",
        submit_url="/restmachine/cloudbroker/qos/limitIO",
        clearForm=False,
    )

    popup.addMessage(
        "Value won't be updated if field is empty. Enter 0 to remove IO limitation."
    )
    popup.addText(
        "Total iops per sec",
        "total_iops_sec",
        type="number",
        value=iotune.get("total_iops_sec", ""),
    )
    popup.addText(
        "Read iops per sec",
        "read_iops_sec",
        type="number",
        value=iotune.get("read_iops_sec", ""),
    )
    popup.addText(
        "Write iops per sec",
        "write_iops_sec",
        type="number",
        value=iotune.get("write_iops_sec", ""),
    )
    popup.addText(
        "Total bytes per sec",
        "total_bytes_sec",
        type="number",
        value=iotune.get("total_bytes_sec", ""),
    )
    popup.addText(
        "Total read bytes per sec",
        "read_bytes_sec",
        type="number",
        value=iotune.get("read_bytes_sec", ""),
    )
    popup.addText(
        "Total write bytes per sec",
        "write_bytes_sec",
        type="number",
        value=iotune.get("write_bytes_sec", ""),
    )
    popup.addText(
        "Maximum total bytes per sec",
        "total_bytes_sec_max",
        type="number",
        value=iotune.get("total_bytes_sec_max", ""),
    )
    popup.addText(
        "Maximum read bytes per sec",
        "read_bytes_sec_max",
        type="number",
        value=iotune.get("read_bytes_sec_max", ""),
    )
    popup.addText(
        "Maximum write bytes per sec",
        "write_bytes_sec_max",
        type="number",
        value=iotune.get("write_bytes_sec_max", ""),
    )
    popup.addText(
        "Maximum total iops per sec",
        "total_iops_sec_max",
        type="number",
        value=iotune.get("total_iops_sec_max", ""),
    )
    popup.addText(
        "Maximum read iops per sec",
        "read_iops_sec_max",
        type="number",
        value=iotune.get("read_iops_sec_max", ""),
    )
    popup.addText(
        "Maximum write iops per sec",
        "write_iops_sec_max",
        type="number",
        value=iotune.get("write_iops_sec_max", ""),
    )
    popup.addText(
        "Iops size per sec",
        "size_iops_sec",
        type="number",
        value=iotune.get("size_iops_sec", ""),
    )

    popup.addHiddenField("diskId", disk.id)
    popup.write_html(page)

    return params
