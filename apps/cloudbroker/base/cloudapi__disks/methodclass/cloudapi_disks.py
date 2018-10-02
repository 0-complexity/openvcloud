from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import authenticator, resourcestatus
from cloudbrokerlib.baseactor import BaseActor
from CloudscalerLibcloud.compute.drivers.libvirt_driver import (
    OpenvStorageVolume,
    OpenvStorageISO,
    PhysicalVolume,
)
import time

MIN_IOPS = 80


class cloudapi_disks(BaseActor):
    """
    API Actor api, this actor is the final api a enduser uses to manage his resources

    """

    def __init__(self):
        super(cloudapi_disks, self).__init__()
        self._minimum_days_of_credit_required = float(
            self.hrd.get(
                "instance.openvcloud.cloudbroker.creditcheck.daysofcreditrequired"
            )
        )

    def getStorageVolume(self, disk, provider, node=None):
        if not isinstance(disk, dict):
            disk = disk.dump()

        volumeclass = OpenvStorageVolume
        name = disk["name"]
        if disk["type"] in ("M", "C"):
            volumeclass = OpenvStorageISO
        elif disk["type"] == "P":
            volumeclass = PhysicalVolume
        elif disk["type"] == "D":
            name = str(disk["id"])

        volume = volumeclass(
            id=disk["referenceId"],
            name=name,
            size=disk["sizeMax"],
            driver=provider,
            extra={"node": node},
            iotune=disk["iotune"],
            order=disk["order"],
        )
        return volume

    def get_max_size(self, gid, type):
        dtype = self.models.disktype.get(type)
        provider = provider = self.cb.getProviderByGID(gid)
        block_size = provider.get_vpool_blocksize(dtype.vpool)
        return int((512 * block_size) / (dtype.cacheratio / 100.0))

    @authenticator.auth(acl={"account": set("C")})
    def create(
        self,
        accountId,
        gid,
        name,
        description,
        size=10,
        type="D",
        ssdSize=0,
        iops=2000,
        **kwargs
    ):
        """
        Create a disk

        :param accountId: id of account
        :param gid :id of the grid
        :param diskName: name of disk
        :param description: optional description of disk
        :param size: size in GBytes, default is 10
        :param type: (B;D;T)  B=Boot;D=Data;T=Temp, default is B
        :return the id of the created disk

        """
        account = self.models.account.get(accountId)
        if account.status in resourcestatus.Account.INVALID_STATES:
            raise exceptions.BadRequest("Can not create a disk on deleted Account")
        with self.models.account.lock(accountId):
            # Validate that enough resources are available in the account CU limits to add the disk
            j.apps.cloudapi.accounts.checkAvailableMachineResources(
                accountId, vdisksize=size
            )
            disk, _ = self.create_disk(accountId, gid, name, description, size, type, iops)
            return disk.id

    def create_disk(
        self,
        accountId,
        gid,
        name,
        description,
        size=10,
        type="D",
        iops=2000,
        physicalSource=None,
        nid=None,
        order=None,
        imageId=None,
        cloudinitdata=None,
        **kwargs
    ):
        max_size = self.get_max_size(gid, type)
        if size > max_size and type != "P":
            raise exceptions.BadRequest(
                "Disk size can not be bigger than {} GB".format(max_size)
            )
        if type == "P" and not (physicalSource and nid):
            raise exceptions.BadRequest(
                "Need to specify both node id and physical source for disk of type 'P'"
            )

        image = None
        if imageId:
            if type != "B":
                raise exceptions.BadRequest(
                    "Can only create disk based on template for a Boot disk"
                )
            imaged = self.models.image.searchOne({"id": imageId})
            if not imaged:
                raise exceptions.BadRequest(
                    "Could not find image with id {}".format(imageId)
                )
            image = self.models.image.new()
            image.load(imaged)
            if image.accountId and image.accountId != accountId:
                raise exceptions.BadRequest(
                    "Image does not belong to account {}".format(accountId)
                )

        types = self.models.disktype.search({"id": type})[1:]
        if not types:
            raise exceptions.BadRequest("Disk type not found")

        disk = self.models.disk.new()
        disk.name = name
        disk.descr = description
        disk.sizeMax = int(size)
        disk.type = type
        disk.gid = gid
        disk.order = order
        disk.status = resourcestatus.Disk.MODELED
        disk.iotune = {"total_iops_sec": iops}
        disk.accountId = accountId
        disk.id = self.models.disk.set(disk)[0]
        dtype = self.models.disktype.get(type)
        try:
            provider = self.cb.getProviderByGID(gid)
            if type == "P":
                volumeid = "file://{source}?id={nid}".format(
                    source=physicalSource, nid=nid
                )
                disk.referenceId = volumeid
                volume = self.getStorageVolume(disk, provider)
            elif type == "B" and imageId:
                volume, edgeclient = provider.create_disk(name, size, image)
                volume.edgeclient = edgeclient
                disk.referenceId = volume.id
            elif type == "M":
                volume = provider.create_metadata_iso(**cloudinitdata)
                disk.referenceId = volume.id
            else:
                volume = provider.create_volume(
                    disk.sizeMax, disk.id, dtype.vpool, type
                )
                volume.iotune = disk.iotune
                disk.referenceId = volume.id
            disk.status = resourcestatus.Disk.CREATED
        except:
            self.models.disk.delete(disk.id)
            raise
        self.models.disk.set(disk)
        return disk, volume

    @authenticator.auth(acl={"account": set("C")})
    def limitIO(
        self,
        diskId,
        iops,
        total_bytes_sec,
        read_bytes_sec,
        write_bytes_sec,
        total_iops_sec,
        read_iops_sec,
        write_iops_sec,
        total_bytes_sec_max,
        read_bytes_sec_max,
        write_bytes_sec_max,
        total_iops_sec_max,
        read_iops_sec_max,
        write_iops_sec_max,
        size_iops_sec,
        **kwargs
    ):
        args = locals()

        # validate combinations
        if (iops or total_iops_sec) and (read_iops_sec or write_iops_sec):
            raise exceptions.BadRequest(
                "total and read/write of iops_sec cannot be set at the same time"
            )
        if (total_bytes_sec) and (read_bytes_sec or write_bytes_sec):
            raise exceptions.BadRequest(
                "total and read/write of bytes_sec cannot be set at the same time"
            )
        if (total_bytes_sec_max) and (read_bytes_sec_max or write_bytes_sec_max):
            raise exceptions.BadRequest(
                "total and read/write of bytes_sec_max cannot be set at the same time"
            )
        if (total_iops_sec_max) and (read_iops_sec_max or write_iops_sec_max):
            raise exceptions.BadRequest(
                "total and read/write of iops_sec_max cannot be set at the same time"
            )

        # validate iops
        for arg, val in args.items():
            if arg in (
                "iops",
                "total_iops_sec",
                "read_iops_sec",
                "write_iops_sec",
                "total_iops_sec_max",
                "read_iops_sec_max",
                "write_iops_sec_max",
                "size_iops_sec",
            ):
                if val and val < MIN_IOPS:
                    raise exceptions.BadRequest(
                        "{arg} was set below the minimum iops {min_iops}: {provided_iops} provided".format(
                            arg=arg, min_iops=MIN_IOPS, provided_iops=val
                        )
                    )

        iotune = args.copy()
        iotune.pop("diskId")
        iotune.pop("kwargs")
        iotune.pop("self")
        iops = iotune.pop("iops")
        if iops:
            iotune["total_iops_sec"] = iops
        disk = self.models.disk.get(diskId)
        if disk.status in resourcestatus.Disk.INVALID_STATES:
            raise exceptions.BadRequest("Disk with id %s is not created" % diskId)

        if disk.type == "M":
            raise exceptions.BadRequest("Can't limitIO on a disk of type Meta")

        machine = next(iter(self.models.vmachine.search({"disks": diskId})[1:]), None)
        if not machine:
            raise exceptions.NotFound("Could not find virtual machine beloning to disk")

        disk.iotune = iotune
        self.models.disk.set(disk)
        provider, node, machine = self.cb.getProviderAndNode(machine["id"])
        volume = self.getStorageVolume(disk, provider, node)
        return provider.ex_limitio(volume)

    @authenticator.auth(acl={"account": set("R")})
    def get(self, diskId, **kwargs):
        """
        Get disk details

        :param diskId: id of the disk
        :return: dict with the disk details
        """
        if not self.models.disk.exists(diskId):
            raise exceptions.NotFound("Can not find disk with id %s" % diskId)
        return self.models.disk.get(diskId).dump()

    @authenticator.auth(acl={"account": set("R")})
    def list(self, accountId, type, **kwargs):
        """
        List the created disks belonging to an account

        :param accountId: id of accountId the disks belongs to
        :param type: type of type of the disks
        :return: list with every element containing details of a disk as a dict
        """
        query = {
            "accountId": {"$in": [accountId, None]},
            "status": {"$ne": resourcestatus.Account.DESTROYED},
        }
        if type:
            query["type"] = type
        disks = self.models.disk.search(query)[1:]
        diskids = [disk["id"] for disk in disks]
        query = {"disks": {"$in": diskids}}
        vms = self.models.vmachine.search(
            {"$query": query, "$fields": ["disks", "id"]}
        )[1:]
        vmbydiskid = dict()
        for vm in vms:
            for diskid in vm["disks"]:
                vmbydiskid[diskid] = vm["id"]
        for disk in disks:
            disk["machineId"] = vmbydiskid.get(disk["id"])
        return disks

    @authenticator.auth(acl={"cloudspace": set("X")})
    def delete(
        self, diskId, detach, permanently=False, name=None, reason=None, **kwargs
    ):
        """
        Delete a disk

        :param diskId: id of disk to delete
        :param detach: detach disk from machine first
        :return True if disk was deleted successfully
        """
        if not self.models.disk.exists(diskId):
            return True
        disk = self.models.disk.get(diskId)
        if name and disk.name != name:
            raise exceptions.BadRequest("Incorrect disk name specified")
        if disk.status == resourcestatus.Disk.DESTROYED:
            return True
        if disk.type == "C":
            machines = self.models.vmachine.count(
                {
                    "tags": {"$regex": "cdrom:%s($|\D)" % disk.id},
                    "status": {"$ne": resourcestatus.Machine.DESTROYED},
                }
            )
            if machines:
                raise exceptions.Conflict("Cannot delete a used disk")
        else:
            machines = self.models.vmachine.search(
                {"disks": diskId, "status": {"$ne": resourcestatus.Machine.DESTROYED}}
            )[1:]

        if machines and not detach:
            raise exceptions.Conflict("Can not delete disk which is attached")
        elif machines:
            j.apps.cloudapi.machines.detachDisk(
                machineId=machines[0]["id"], diskId=diskId, **kwargs
            )
        if permanently:
            provider = self.cb.getProviderByGID(disk.gid)
            volume = self.getStorageVolume(disk, provider)
            provider.destroy_volume(volume)
            disk.status = resourcestatus.Disk.DESTROYED
        else:
            disk.status = resourcestatus.Disk.TOBEDELETED
        disk.deletionTime = int(time.time())
        self.models.disk.set(disk)
        return True

    @authenticator.auth(acl={"account": set("C")})
    def resize(self, diskId, size, **kwargs):
        """
        Resize a Disk
        stop and start required for the changes to be reflected
        :param diskId: id of disk to delete
        :param size: the new size of the disk in GB
        """
        disk = self.models.disk.get(diskId)
        max_size = self.get_max_size(disk.gid, disk.type)
        if size > max_size:
            raise exceptions.BadRequest(
                "Size can not be more than {}G".format(max_size)
            )
        if disk.type == "M":
            raise exceptions.BadRequest("Can't resize a disk of type Meta")
        if disk.sizeMax >= size:
            raise exceptions.BadRequest(
                "The specified size is smaller than or equal the original size"
            )
        if disk.status in resourcestatus.Disk.INVALID_STATES:
            raise exceptions.BadRequest("Disk with id %s is not created" % diskId)

        machine = next(iter(self.models.vmachine.search({"disks": diskId})[1:]), None)
        with self.models.account.lock(disk.accountId):
            if machine:
                # Validate that enough resources are available in the CU limits to add the disk
                j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
                    machine["cloudspaceId"], vdisksize=size
                )
                provider, _, _ = self.cb.getProviderAndNode(machine["id"])
                machine_id = machine["referenceId"]
            else:
                # Validate that enough resources are available in the CU limits to add the disk
                j.apps.cloudapi.accounts.checkAvailableMachineResources(
                    disk.accountId, vdisksize=size
                )
                provider = self.cb.getProviderByGID(disk.gid)
                machine_id = None

            volume = self.getStorageVolume(disk, provider)
            disk.sizeMax = size
            disk_info = {"referenceId": disk.referenceId, "machineRefId": machine_id}
            res = provider.ex_extend_disk(volume.vdiskguid, size, disk_info)
            self.models.disk.set(disk)
            if not res:
                raise exceptions.Accepted(False)
            return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def restore(self, diskId, reason, **kwargs):
        disk = self.models.disk.searchOne({"id": diskId})
        account = self.models.account.get(disk["accountId"])
        if not disk or disk["status"] == resourcestatus.Disk.DESTROYED:
            raise exceptions.NotFound("Couldn't find disk with id: %s" % diskId)
        if (
            account.status in resourcestatus.Account.INVALID_STATES
            and "diskrestore" not in kwargs
        ):
            raise exceptions.BadRequest("Cannot restore a disk on a deleted account")
        if disk["status"] != resourcestatus.Disk.TOBEDELETED:
            raise exceptions.BadRequest(
                "Cannot restore an attached or non deleted disk"
            )
        self.models.disk.updateSearch(
            {"id": diskId},
            {"$set": {"status": resourcestatus.Disk.CREATED, "deletionTime": 0}},
        )
        return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def deleteDisks(self, diskIds, reason, permanently=False, **kwargs):
        for diskId in diskIds:
            self.delete(diskId, False, permanently, reason=reason)
        return True

    @authenticator.auth(groups=["level1", "level2", "level3"])
    def addType(
        self, id, description, vpool=None, cacheratio=None, snapshotable=True, **kwargs
    ):
        if cacheratio <= 0 and vpool:
            raise exceptions.BadRequest("Cache Ratio must be larger than Zero")
        dtype = self.models.disktype.searchOne({"id": id})
        if dtype:
            raise exceptions.BadRequest(
                "Disk type with id: {} already exits, Please choose other name".format(
                    id
                )
            )
        disk_type = self.models.disktype.new()
        disk_type.id = id
        disk_type.description = description
        disk_type.snapshotable = snapshotable
        disk_type.vpool = vpool
        disk_type.cacheratio = cacheratio
        self.models.disktype.set(disk_type)
        return True

    @authenticator.auth()
    def updateType(
        self,
        id,
        description=None,
        vpool=None,
        cacheratio=None,
        snapshotable=None,
        **kwargs
    ):
        dtype = self.models.disktype.searchOne({"id": id})
        if not dtype:
            raise exceptions.BadRequest("Can not find Disk Type with id: {}".format(id))

        if cacheratio <= 0 and (dtype["vpool"] or vpool):
            raise exceptions.BadRequest("Cache Ratio must be larger than Zero")
        update = {}
        if description:
            update["description"] = description
        if vpool:
            update["vpool"] = vpool
        if cacheratio:
            update["cacheratio"] = cacheratio
        if snapshotable == "False":
            update["snapshotable"] = False
        elif snapshotable == "True":
            update["snapshotable"] = True

        if update:
            self.models.disktype.updateSearch({"id": id}, {"$set": update})

    @authenticator.auth(groups=["level1", "level2", "level3"])
    def deleteTypes(self, typeIds, **kwargs):
        if not isinstance(typeIds, list):
            typeIds = [typeIds]
        for typeId in typeIds:
            dtype = self.models.disktype.searchOne({"id": typeId})
            if not dtype:
                raise exceptions.BadRequest(
                    "Can not find Disk Type with id: {}".format(typeId)
                )
        for typeId in typeIds:
            self.models.disktype.delete(typeId)
        return True

    @authenticator.auth(groups=["level1", "level2", "level3"])
    def deleteType(self, id, **kwargs):
        dtype = self.models.disktype.searchOne({"id": id})
        if not dtype:
            raise exceptions.BadRequest("Can not find Disk Type with id: {}".format(id))
        self.models.disktype.delete(id)
        return True

    def listTypes(self, **kwargs):
        """
        List the disk types Ids
        """
        types = self.models.disktype.search({})
        return types

