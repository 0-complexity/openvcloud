from JumpScale import j
from cloudbrokerlib import authenticator, resourcestatus
from cloudbrokerlib.authenticator import auth
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal.async import async
from JumpScale.portal.portal import exceptions
import gevent
import netaddr
import time


class cloudbroker_machine(BaseActor):
    def __init__(self):
        super(cloudbroker_machine, self).__init__()
        self.libvirtcl = j.clients.osis.getNamespace("libvirt")
        self.vfwcl = j.clients.osis.getNamespace("vfw")

    def _checkMachine(self, machineId):
        vmachines = self.models.vmachine.search({"id": machineId})[1:]
        if not vmachines:
            raise exceptions.NotFound("Machine with id %s does not exists" % machineId)

        return vmachines[0]

    @auth(groups=["level1", "level2", "level3"])
    def create(
        self,
        cloudspaceId,
        name,
        description,
        imageId,
        disksize,
        datadisks,
        sizeId=None,
        vcpus=None,
        memory=None,
        **kwargs
    ):
        if sizeId == -1:
            sizeId = None
        return j.apps.cloudapi.machines.create(
            cloudspaceId=cloudspaceId,
            name=name,
            description=description,
            sizeId=sizeId,
            imageId=imageId,
            disksize=disksize,
            datadisks=datadisks,
            vcpus=vcpus,
            memory=memory,
            **kwargs
        )

    @auth(groups=["level1", "level2", "level3"])
    def createOnStack(
        self,
        cloudspaceId,
        name,
        description,
        imageId,
        disksize,
        stackid,
        datadisks,
        userdata=None,
        sizeId=None,
        vcpus=None,
        memory=None,
        **kwargs
    ):
        """
        Create a machine on a specific stackid
        param:cloudspaceId id of space in which we want to create a machine
        param:name name of machine
        param:description optional description
        param:sizeId id of the specific size
        param:imageId id of the specific image
        param:disksize size of base volume
        param:stackid id of the stack
        param:datadisks list of disk sizes
        param:vcpu int number of cpu to assign to machine 
        param:memory int ammount of memory to assign to machine
        result bool
        """
        if sizeId == -1:
            sizeId = None
        machine, auth, volumes, cloudspace = j.apps.cloudapi.machines._prepare_machine(
            cloudspaceId,
            name,
            description,
            imageId,
            disksize,
            datadisks,
            sizeId,
            vcpus,
            memory,
            userdata,
        )
        machineId = self.cb.machine.create(
            machine, auth, cloudspace, volumes, imageId, stackid, userdata
        )
        gevent.spawn(
            self.cb.cloudspace.update_firewall,
            cloudspace,
            ctx=j.core.portal.active.requestContext,
        )
        kwargs["ctx"].env["tags"] += " machineId:{}".format(machineId)
        return machineId

    def _validateMachineRequest(self, machineId):
        machineId = int(machineId)
        if not self.models.vmachine.exists(machineId):
            raise exceptions.NotFound("Machine ID %s was not found" % machineId)

        vmachine = self.models.vmachine.get(machineId)

        if vmachine.status == resourcestatus.Machine.DESTROYED or not vmachine.status:
            raise exceptions.BadRequest("Machine %s is invalid" % machineId)

        return vmachine

    @auth(groups=["level1", "level2", "level3"])
    def prepareForMigration(self, cloudspaceId, machine, **kwargs):
        if not self.models.cloudspace.exists(cloudspaceId):
            raise exceptions.BadRequest(
                "Target cloudspace {} does not exists".format(cloudspaceId)
            )
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        totaldisksize = 0
        # pop all extra data
        vcpus = machine.pop("vcpus")
        memory = machine.pop("memory")
        networkId = machine.pop("networkId")
        sourcedisks = machine.pop("disks")
        machine.pop("cloneReference")
        machine.pop("clone")
        for disk in sourcedisks:
            totaldisksize += disk["sizeMax"]
        image = self.models.image.searchOne({"name": machine["imagename"]})
        if image is None:
            raise exceptions.BadRequest(
                "Could not find image with name {}".format(machine["imagename"])
            )
        if networkId != cloudspace.networkId:
            raise exceptions.BadRequest("NetworkId does not match vm")

        j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
            cloudspace.id, vcpus, memory / 1024.0, totaldisksize
        )

        externalnetworks = self.models.externalnetwork.search(
            {"$fields": ["network", "id", "subnetmask"]}
        )[1:]
        # check external networks of vm
        for nic in machine["nics"]:
            if nic["type"] == "PUBLIC":
                ipAddress = nic["ipAddress"]
                for extnetwork in externalnetworks:
                    network = netaddr.IPNetwork(
                        "{network}/{subnetmask}".format(**extnetwork)
                    )
                    if netaddr.IPNetwork(ipAddress).ip in network:
                        break
                else:
                    raise exceptions.BadRequest(
                        "Could not migrate VM in external network {} which does not exist"
                    )
                tags = j.core.tags.getObject(nic["params"], casesensitive=True)
                tags.tags["externalnetworkId"] = str(extnetwork["id"])
                nic["params"] = str(tags)

        diskids = []
        disks = []
        for diskdata in sourcedisks:
            disk = self.models.disk.new()
            disk.load(diskdata)
            disk.id = None
            disk.guid = None
            disk.referenceId = None
            disk.gid = cloudspace.gid
            disk.id, _, _ = self.models.disk.set(disk)
            diskids.append(disk.id)
            disks.append(disk)

        vm = self.models.vmachine.new()
        vm.load(machine)
        vm.cloudspaceId = cloudspace.id
        vm.memory = memory
        vm.vcpus = vcpus
        vm.imageId = image["id"]
        vm.status = resourcestatus.Machine.MIGRATING
        vm.id = None
        vm.guid = None
        vm.disks = diskids
        vm.id, _, _ = self.models.vmachine.set(vm)

        # now lets create empty volumes
        provider = self.cb.getProviderByGID(cloudspace.gid)
        for disk in disks:
            name = ""
            data = False
            size = disk.sizeMax
            if disk.type == "B":
                name = "vm-{0}/bootdisk-vm-{0}".format(vm.id)
            elif disk.type == "M":
                name = "vm-{0}/cloud-init-vm-{0}".format(vm.id)
                size = 0.1
            elif disk.type == "D":
                name = str(disk.id)
                data = True
            volume = provider.create_volume(size, name, data)
            disk.referenceId = volume.id
            self.models.disk.set(disk)

        # prepare network on target node
        self.cb.chooseStack(vm)
        provider, node, machine = self.cb.getProviderAndNode(vm.id)
        # set status back to migrating
        self.models.vmachine.updateSearch(
            {"id": vm.id}, {"$set": {"status": resourcestatus.Machine.MIGRATING}}
        )
        provider._ensure_network(node)
        # return data needed for migration
        xml = provider.get_xml(node)
        return {"id": vm.id, "xml": xml, "stackId": machine.stackId}

    @auth(groups=["level1", "level2", "level3"])
    def destroy(self, machineId, reason, permanently=False, name=None, **kwargs):
        j.apps.cloudapi.machines.delete(
            machineId=int(machineId), permanently=permanently, name=name
        )
        return True

    @auth(groups=["level3"])
    def destroyMachines(self, machineIds, reason, permanently=False, **kwargs):
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._destroyMachines,
            args=(machineIds, permanently, reason, ctx),
            kwargs={},
            title="Destroying Machines",
            success="Machines destroyed successfully",
            error="Failed to destroy machines",
        )

    def _destroyMachines(self, machineIds, permanently, reason, ctx):
        for idx, machineId in enumerate(machineIds):
            ctx.events.sendMessage(
                "Destroying Machine",
                "Destroying Machine %s/%s" % (idx + 1, len(machineIds)),
            )
            try:  # BULK ACTION
                self.destroy(machineId, reason, permanently)
            except exceptions.BadRequest:
                pass

    @auth(groups=["level1", "level2", "level3"])
    def start(self, machineId, reason, diskId=None, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        if "start" in vmachine.tags.split(" "):
            j.apps.cloudbroker.machine.untag(vmachine.id, "start")
        j.apps.cloudapi.machines.start(machineId=machineId, diskId=diskId)

    @auth(groups=["level1", "level2", "level3"])
    def restore(self, machineId, reason, **kwargs):
        """
        Restore a deleted machine

        :param machineId: id of the machine
        """
        return j.apps.cloudapi.machines.restore(machineId, reason)

    @auth(groups=["level1", "level2", "level3"])
    def startMachines(self, machineIds, reason, **kwargs):
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._startMachines,
            args=(machineIds, reason, ctx),
            kwargs={},
            title="Starting machines",
            success="Machines started successfully",
            error="Failed to start machines",
        )

    def _startMachines(self, machineIds, reason, ctx):
        for idx, machineId in enumerate(machineIds):
            ctx.events.sendMessage(
                "Starting", "Starting Machine %s/%s" % (idx + 1, len(machineIds))
            )
            try:  # BULK ACTION
                self.start(machineId, reason)
            except exceptions.BadRequest:
                pass

    @auth(groups=["level1", "level2", "level3"])
    def stop(self, machineId, reason, **kwargs):
        j.apps.cloudapi.machines.stop(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def stopMachines(self, machineIds, reason, **kwargs):
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._stopMachines,
            args=(machineIds, reason, ctx),
            kwargs={},
            title="Stopping machines",
            success="Machines stopped successfully",
            error="Failed to stop machines",
        )

    def _stopMachines(self, machineIds, reason, ctx):
        runningMachineIds = []
        for machineId in machineIds:
            try:  # BULK ACTION
                vmachine = self._validateMachineRequest(machineId)
                if vmachine.status in resourcestatus.Machine.UP_STATES:
                    runningMachineIds.append(machineId)
            except exceptions.BadRequest:
                pass

        for idx, machineId in enumerate(runningMachineIds):
            ctx.events.sendMessage(
                "Stopping Machine",
                "Stopping Machine %s/%s" % (idx + 1, len(runningMachineIds)),
            )
            j.apps.cloudapi.machines.stop(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def pause(self, machineId, reason, **kwargs):
        j.apps.cloudapi.machines.pause(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def resume(self, machineId, reason, **kwargs):
        j.apps.cloudapi.machines.resume(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def reboot(self, machineId, reason, **kwargs):
        j.apps.cloudapi.machines.reboot(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def get(self, machineId, **kwargs):
        return self._checkMachine(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def rebootMachines(self, machineIds, reason, **kwargs):
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._rebootMachines,
            args=(machineIds, reason, ctx),
            kwargs={},
            title="Rebooting machines",
            success="Machines rebooted successfully",
            error="Failed to reboot machines",
        )

    def _rebootMachines(self, machineIds, reason, ctx):
        for idx, machineId in enumerate(machineIds):
            ctx.events.sendMessage(
                "Rebooting Machine",
                "Rebooting Machine %s/%s" % (idx + 1, len(machineIds)),
            )
            try:  # BULK ACTION
                self.reboot(machineId, reason)
            except exceptions.BadRequest:
                pass

    @auth(groups=["level1", "level2", "level3"])
    def snapshot(self, machineId, snapshotName, reason, force=False, **kwargs):
        j.apps.cloudapi.machines.snapshot(
            machineId=machineId, name=snapshotName, force=force
        )

    @auth(groups=["level1", "level2", "level3"])
    def rollbackSnapshot(self, machineId, reason, name=None, epoch=None, **kwargs):
        j.apps.cloudapi.machines.rollbackSnapshot(machineId=machineId, name=name, epoch=epoch)

    @auth(groups=["level1", "level2", "level3"])
    def deleteSnapshot(self, machineId, epoch, reason, **kwargs):
        j.apps.cloudapi.machines.deleteSnapshot(machineId=machineId, epoch=epoch)

    @auth(groups=["level1", "level2", "level3"])
    def clone(self, machineId, cloneName, reason, **kwargs):
        j.apps.cloudapi.machines.clone(machineId=machineId, name=cloneName)

    @auth(groups=["level1", "level2", "level3"])
    @async(
        "Moving Virtual Machine",
        "Finished Moving Virtual Machine",
        "Failed to move Virtual Machine",
    )
    def moveToDifferentComputeNode(
        self, machineId, reason, targetStackId=None, force=False, **kwargs
    ):
        vmachine = self._validateMachineRequest(machineId)
        if self.models.disk.count({"id": {"$in": vmachine.disks}, "type": "P"}) > 0:
            raise exceptions.BadRequest("Can't move a vm with physical disks attached")
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        source_stack = self.models.stack.get(vmachine.stackId)
        if not targetStackId:
            targetStackId = self.cb.getBestStack(
                cloudspace.gid, vmachine.imageId, memory=vmachine.memory
            )["id"]

        stack = self.models.stack.get(targetStackId)
        if not stack.status == "ENABLED":
            raise exceptions.BadRequest("Target Stack is not active")

        target_provider = self.cb.getProviderByStackId(targetStackId)
        if target_provider.gid != source_stack.gid:
            raise exceptions.BadRequest(
                "Target stack %s is not on some grid as source" % target_provider.uri
            )

        if vmachine.status != resourcestatus.Machine.HALTED:
            # create network on target node
            node = self.cb.getNode(vmachine, target_provider)
            migrated = target_provider.ex_migrate(
                node, self.cb.getProviderByStackId(vmachine.stackId), force
            )
            if migrated == -1:
                vmachine.status = resourcestatus.Machine.HALTED
            elif migrated == 0:
                args = {"networkid": cloudspace.networkId}
                self.cb.agentcontroller.executeJumpscript(
                    "greenitglobe",
                    "cleanup_network",
                    nid=int(source_stack.referenceId),
                    gid=source_stack.gid,
                    args=args,
                )
        vmachine.stackId = targetStackId
        self.models.vmachine.set(vmachine)

    @auth(groups=["level1", "level2", "level3"])
    def listExports(self, status, machineId, **kwargs):
        machineId = int(machineId)
        query = {"status": status, "machineId": machineId}
        exports = self.models.vmexport.search(query)[1:]
        exportresult = []
        for exp in exports:
            exportresult.append(
                {
                    "status": exp["status"],
                    "type": exp["type"],
                    "storagetype": exp["storagetype"],
                    "machineId": exp["machineId"],
                    "id": exp["id"],
                    "name": exp["name"],
                    "timestamp": exp["timestamp"],
                }
            )
        return exportresult

    @auth(groups=["level1", "level2", "level3"])
    def tag(self, machineId, tagName, **kwargs):
        """
        Adds a tag to a machine, useful for indexing and following a (set of) machines
        param:machineId id of the machine to tag
        param:tagName tag
        """
        vmachine = self._validateMachineRequest(machineId)
        tags = j.core.tags.getObject(vmachine.tags)
        if tags.labelExists(tagName):
            raise exceptions.Conflict(
                "Tag %s is already assigned to this vMachine" % tagName
            )

        tags.labelSet(tagName)
        vmachine.tags = tags.tagstring
        self.models.vmachine.set(vmachine)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def untag(self, machineId, tagName, **kwargs):
        """
        Removes a specific tag from a machine
        param:machineId id of the machine to untag
        param:tagName tag
        """
        vmachine = self._validateMachineRequest(machineId)
        tags = j.core.tags.getObject(vmachine.tags)
        if not tags.labelExists(tagName):
            raise exceptions.NotFound("vMachine does not have tag %s" % tagName)

        tags.labelDelete(tagName)
        vmachine.tags = tags.tagstring
        self.models.vmachine.set(vmachine)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def list(
        self, tag=None, computeNode=None, accountName=None, cloudspaceId=None, **kwargs
    ):
        """
        List the undestroyed machines based on specific criteria
        At least one of the criteria needs to be passed
        param:tag a specific tag
        param:computenode name of a specific computenode
        param:accountname specific account
        param:cloudspaceId specific cloudspace
        """
        if not tag and not computeNode and not accountName and not cloudspaceId:
            raise exceptions.BadRequest("At least one parameter must be passed")
        query = dict()
        if tag:
            query["tags"] = tag
        if computeNode:
            stacks = self.models.stack.search({"referenceId": computeNode})[1:]
            if stacks:
                stack_id = stacks[0]["id"]
                query["stackId"] = stack_id
            else:
                return list()
        if accountName:
            accounts = self.models.account.search({"name": accountName})[1:]
            if accounts:
                account_id = accounts[0]["id"]
                cloudspaces = self.models.cloudspace.search({"accountId": account_id})[
                    1:
                ]
                if cloudspaces:
                    cloudspaces_ids = [cs["id"] for cs in cloudspaces]
                    query["cloudspaceId"] = {"$in": cloudspaces_ids}
                else:
                    return list()
            else:
                return list()
        if cloudspaceId:
            query["cloudspaceId"] = cloudspaceId

        query["status"] = {"$ne": "destroyed"}
        return self.models.vmachine.search(query)[1:]

    @auth(groups=["level1", "level2", "level3"])
    def stopForAbusiveResourceUsage(self, accountId, machineId, reason, **kwargs):
        """If a machine is abusing the system and violating the usage policies it can be stopped using this procedure.
        A ticket will be created for follow up and visibility, the machine stopped, the image put on slower storage and the ticket is automatically closed if all went well.
        Use with caution!
        @param:accountId int,,Account ID, extra validation for preventing a wrong machineId
        @param:machineId int,,Id of the machine
        @param:reason str,,Reason
        """
        machineId = int(machineId)
        vmachine = self._validateMachineRequest(machineId)

        stack = self.models.stack.get(vmachine.stackId)
        args = {"machineId": vmachine.id, "nodeId": vmachine.referenceId}
        self.cb.executeJumpscript(
            "cloudscalers",
            "vm_stop_for_abusive_usage",
            gid=stack.gid,
            nid=stack.referenceId,
            args=args,
            wait=False,
        )

    @auth(groups=["level1", "level2", "level3"])
    def backupAndDestroy(self, accountId, machineId, reason, **kwargs):
        """
        * Create a ticketjob
        * Call the backup method
        * Destroy the machine
        * Close the ticket
        """
        vmachine = self._validateMachineRequest(machineId)
        args = {
            "accountId": accountId,
            "machineId": machineId,
            "reason": reason,
            "vmachineName": vmachine.name,
            "cloudspaceId": vmachine.cloudspaceId,
        }
        self.cb.executeJumpscript(
            "cloudscalers",
            "vm_backup_destroy",
            gid=j.application.whoAmI.gid,
            nid=j.application.whoAmI.nid,
            args=args,
            wait=False,
        )

    @auth(groups=["level1", "level2", "level3"])
    def listSnapshots(self, machineId, **kwargs):
        return j.apps.cloudapi.machines.listSnapshots(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def getHistory(self, machineId, **kwargs):
        return j.apps.cloudapi.machines.getHistory(machineId=machineId, size=10)

    @auth(groups=["level1", "level2", "level3"])
    def listPortForwards(self, machineId, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        vfwkey = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        results = list()
        machineips = [
            nic.ipAddress for nic in vmachine.nics if not nic.ipAddress == "Undefined"
        ]
        if self.vfwcl.virtualfirewall.exists(vfwkey):
            vfw = self.vfwcl.virtualfirewall.get(vfwkey).dump()
            for idx, forward in enumerate(vfw["tcpForwardRules"]):
                if forward["toAddr"] in machineips:
                    forward["id"] = idx
                    results.append(forward)
        return results

    @auth(groups=["level1", "level2", "level3"])
    def createPortForward(self, machineId, localPort, destPort, proto, **kwargs):
        machineId = int(machineId)
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        j.apps.cloudapi.portforwarding.create(
            cloudspaceId=cloudspace.id,
            publicIp=cloudspace.externalnetworkip,
            publicPort=destPort,
            machineId=vmachine.id,
            localPort=localPort,
            protocol=proto,
        )

    @auth(groups=["level1", "level2", "level3"])
    def deletePortForward(self, machineId, publicIp, publicPort, proto, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        j.apps.cloudapi.portforwarding.deleteByPort(
            cloudspaceId=cloudspace.id,
            publicIp=publicIp,
            publicPort=publicPort,
            proto=proto,
        )

    @auth(groups=["level1", "level2", "level3"])
    def addDisk(self, machineId, diskName, description, size=10, iops=2000, **kwargs):
        self._validateMachineRequest(machineId)
        j.apps.cloudapi.machines.addDisk(
            machineId=machineId,
            diskName=diskName,
            description=description,
            size=size,
            type="D",
            iops=iops,
        )

    @auth(groups=["level1", "level2", "level3"])
    def deleteDisk(self, machineId, diskId, **kwargs):
        self._validateMachineRequest(machineId)
        return j.apps.cloudapi.disks.delete(diskId=diskId, detach=True)

    @auth(groups=["level1", "level2", "level3"])
    def createTemplate(self, machineId, templateName, callbackUrl, reason, **kwargs):
        self._validateMachineRequest(machineId)
        j.apps.cloudapi.machines.createTemplate(
            machineId=machineId, templatename=templateName, callbackUrl=callbackUrl
        )

    @auth(groups=["level1", "level2", "level3"])
    def updateMachine(self, machineId, description, name, reason, **kwargs):
        self._validateMachineRequest(machineId)
        j.apps.cloudapi.machines.update(
            machineId=machineId, description=description, name=name
        )

    @auth(groups=["level1", "level2", "level3"])
    def attachExternalNetwork(self, machineId, externalNetworkId, **kwargs):
        return j.apps.cloudapi.machines.attachExternalNetwork(
            machineId=machineId, externalNetworkId=externalNetworkId
        )

    @auth(groups=["level1", "level2", "level3"])
    def detachExternalNetwork(self, machineId, externalNetworkId, **kwargs):
        return j.apps.cloudapi.machines.detachExternalNetwork(
            machineId=machineId, externalNetworkId=externalNetworkId
        )

    @auth(groups=["level1", "level2", "level3"])
    def listExternalNetworks(self, machineId, **kwargs):
        return j.apps.cloudapi.machines.listExternalNetworks(machineId=machineId)

    @auth(groups=["level1", "level2", "level3"])
    def addUser(self, machineId, username, accesstype, **kwargs):
        """
        Give a user access rights.
        Access rights can be 'R' or 'W'
        param:machineId id of the machine
        param:username id of the user to give access or emailaddress to invite an external user
        param:accesstype 'R' for read only access, 'W' for Write access
        result bool
        """
        machineId = self._checkMachine(machineId)
        machineId = machineId["id"]
        user = self.cb.checkUser(username, activeonly=False)

        vmachineacl = authenticator.auth().getVMachineAcl(machineId)
        if username in vmachineacl:
            updated = j.apps.cloudapi.machines.updateUser(
                machineId=machineId, userId=username, accesstype=accesstype
            )
            if not updated:
                raise exceptions.PreconditionFailed(
                    "User already has same access level to owning "
                    "account or cloudspace"
                )
        if user:
            j.apps.cloudapi.machines.addUser(
                machineId=machineId, userId=username, accesstype=accesstype
            )
        else:
            raise exceptions.NotFound("User with username %s is not found" % username)

        return True

    @auth(groups=["level1", "level2", "level3"])
    def deleteUser(self, machineId, username, **kwargs):
        """
        Delete a user from the account
        """
        machineId = self._checkMachine(machineId)
        machineId = machineId["id"]
        user = self.cb.checkUser(username)
        if user:
            userId = user["id"]
        else:
            # external user, delete ACE that was added using emailaddress
            userId = username
        j.apps.cloudapi.machines.deleteUser(machineId=machineId, userId=userId)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def resize(self, machineId, sizeId=None, vcpus=None, memory=None, **kwargs):
        if sizeId == -1:
            sizeId = None
        response = j.apps.cloudapi.machines.resize(
            machineId=machineId, sizeId=sizeId, memory=memory, vcpus=vcpus
        )
        if response:
            return "Successfully resized machine"
        else:
            return "Could not apply changes on running machine please stop and start machine for the change to take effect"
