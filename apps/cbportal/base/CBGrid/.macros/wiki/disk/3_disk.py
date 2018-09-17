from CloudscalerLibcloud.compute.drivers.libvirt_driver import PhysicalVolume


def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    diskid = args.requestContext.params.get("id")

    try:
        disk = db.cloudbroker.disk.get(int(diskid))
    except:
        args.doc.applyTemplate({})
        return params
    disk_data = disk.dump()
    machine = next(
        iter(db.cloudbroker.vmachine.search({"disks": disk_data["id"]})[1:]), None
    )
    account = db.cloudbroker.account.searchOne({"id": disk_data["accountId"]})
    disk_data["accountName"] = account["name"] if account else ""
    if machine:
        disk_data["machineId"] = machine["id"]
        disk_data["machineName"] = machine["name"]
    disktypemap = {
        "D": "Data",
        "B": "Boot",
        "M": "Meta",
        "C": "CD-ROM",
        "P": "Physical",
    }
    disk_data["type"] = disktypemap.get(disk_data["type"], disk_data["type"])
    volume = j.apps.cloudapi.disks.getStorageVolume(disk, None)
    if not isinstance(volume, PhysicalVolume):
        disk_data["edgehost"] = volume.edgehost
        disk_data["edgeport"] = volume.edgeport
        disk_data["vdiskguid"] = volume.vdiskguid
    disk_data["edgename"] = volume.name
    disk_data["devicename"] = volume.dev

    for iotune, value in disk_data["iotune"].items():
        if not value:
            disk_data["iotune"][iotune] = ""
    args.doc.applyTemplate(disk_data, False)
    return params
