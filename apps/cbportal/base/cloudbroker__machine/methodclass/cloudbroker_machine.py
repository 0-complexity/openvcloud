from JumpScale import j
from cloudbrokerlib.baseactor import BaseActor, wrap_remote
from JumpScale.portal.portal.auth import auth
from JumpScale.portal.portal.async import async
from JumpScale.portal.portal import exceptions
import ujson


class cloudbroker_machine(BaseActor):

    def __init__(self):
        super(cloudbroker_machine, self).__init__()
        self.libvirtcl = j.clients.osis.getNamespace('libvirt')
        self.vfwcl = j.clients.osis.getNamespace('vfw')
        self.actors = self.cb.actors.cloudapi
        self.acl = j.clients.agentcontroller.get()

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def create(self, cloudspaceId, name, description, sizeId, imageId, disksize, datadisks, **kwargs):
        return self.actors.machines.create(cloudspaceId, name, description, sizeId, imageId, disksize, datadisks)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def createOnStack(self, cloudspaceId, name, description, sizeId, imageId, disksize, stackid, datadisks, **kwargs):
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
        result bool
        """
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        self.cb.machine.validateCreate(cloudspace, name, sizeId, imageId, disksize, 0)
        machine, auth, diskinfo = self.cb.machine.createModel(name, description, cloudspace, imageId, sizeId, disksize, datadisks)
        return self.cb.machine.create(machine, auth, cloudspace, diskinfo, imageId, stackid)

    def _validateMachineRequest(self, machineId):
        machineId = int(machineId)
        if not self.models.vmachine.exists(machineId):
            raise exceptions.NotFound('Machine ID %s was not found' % machineId)

        vmachine = self.models.vmachine.get(machineId)

        if vmachine.status == 'DESTROYED' or not vmachine.status:
            raise exceptions.BadRequest('Machine %s is invalid' % machineId)

        return vmachine

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def destroy(self, machineId, reason, **kwargs):
        self.actors.machines.delete(int(machineId))
        return True

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def start(self, machineId, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.start(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def stop(self, machineId, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.stop(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def pause(self, machineId, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.pause(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def resume(self, machineId, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.resume(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def reboot(self, machineId, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.reboot(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def snapshot(self, machineId, snapshotName, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.snapshot(machineId, snapshotName)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def rollbackSnapshot(self, machineId, snapshotName, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.rollbackSnapshot(machineId, snapshotName)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def deleteSnapshot(self, machineId, snapshotName, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        self.actors.machines.deleteSnapshot(machineId, snapshotName)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def clone(self, machineId, cloneName, reason, **kwargs):
        self._validateMachineRequest(machineId)
        self.actors.machines.clone(machineId, cloneName)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    @async('Moving Virtual Machine', 'Finished Moving Virtual Machine', 'Failed to move Virtual Machine')
    def moveToDifferentComputeNode(self, machineId, reason, targetStackId=None, force=False, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        source_stack = self.models.stack.get(vmachine.stackId)
        if not targetStackId:
            targetStackId = self.cb.getBestProvider(cloudspace.gid, vmachine.imageId)['id']

        target_provider = self.cb.getProviderByStackId(targetStackId)
        if target_provider.client.gid != source_stack.gid:
            raise exceptions.BadRequest('Target stack %s is not on some grid as source' % target_provider.client.uri)

        if vmachine.status != 'HALTED':
            # create network on target node
            self.acl.executeJumpscript('cloudscalers', 'createnetwork', args={'networkid': cloudspace.networkId},
                                       gid=target_provider.client.gid, nid=target_provider.client.id, wait=True)

            node = self.cb.Dummy(id=vmachine.referenceId)
            target_provider.client.ex_migrate(node, self.cb.getProviderByStackId(vmachine.stackId).client, force)
        vmachine.stackId = targetStackId
        self.models.vmachine.set(vmachine)

    @auth(['level1', 'level2', 'level3'])
    def export(self, machineId, name, backuptype, storage, host, aws_access_key, aws_secret_key, bucketname, **kwargs):
        machineId = int(machineId)
        machine = self._validateMachineRequest(machineId)
        stack = self.models.stack.get(machine.stackId)
        storageparameters = {}
        if storage == 'S3':
            if not aws_access_key or not aws_secret_key or not host:
                raise exceptions.BadRequest('S3 parameters are not provided')
            storageparameters['aws_access_key'] = aws_access_key
            storageparameters['aws_secret_key'] = aws_secret_key
            storageparameters['host'] = host
            storageparameters['is_secure'] = True

        storageparameters['storage_type'] = storage
        storageparameters['backup_type'] = backuptype
        storageparameters['bucket'] = bucketname
        storageparameters['mdbucketname'] = bucketname

        storagepath = '/mnt/vmstor/vm-%s' % machineId
        nid = int(stack.referenceId)
        gid = stack.gid
        args = {'path': storagepath, 'name': name, 'machineId': machineId,
                'storageparameters': storageparameters, 'nid': nid, 'backup_type': backuptype}
        guid = self.acl.executeJumpscript(
            'cloudscalers', 'cloudbroker_export', j.application.whoAmI.nid, gid=gid, args=args, wait=False)['guid']
        return guid

    @auth(['level1', 'level2', 'level3'])
    def restore(self, vmexportId, nid, destinationpath, aws_access_key, aws_secret_key, **kwargs):
        vmexportId = int(vmexportId)
        nid = int(nid)
        vmexport = self.models.vmexport.get(vmexportId)
        if not vmexport:
            raise exceptions.NotFound('Export definition with id %s not found' % vmexportId)
        storageparameters = {}

        if vmexport.storagetype == 'S3':
            if not aws_access_key or not aws_secret_key:
                raise exceptions.BadRequest('S3 parameters are not provided')
            storageparameters['aws_access_key'] = aws_access_key
            storageparameters['aws_secret_key'] = aws_secret_key
            storageparameters['host'] = vmexport.server
            storageparameters['is_secure'] = True

        storageparameters['storage_type'] = vmexport.storagetype
        storageparameters['bucket'] = vmexport.bucket
        storageparameters['mdbucketname'] = vmexport.bucket

        metadata = ujson.loads(vmexport.files)

        args = {'path': destinationpath, 'metadata': metadata, 'storageparameters': storageparameters, 'nid': nid}

        id = self.acl.executeJumpscript(
            'cloudscalers', 'cloudbroker_import', j.application.whoAmI.nid, args=args, wait=False)['result']
        return id

    @auth(['level1', 'level2', 'level3'])
    def listExports(self, status, machineId, **kwargs):
        machineId = int(machineId)
        query = {'status': status, 'machineId': machineId}
        exports = self.models.vmexport.search(query)[1:]
        exportresult = []
        for exp in exports:
            exportresult.append({'status': exp['status'], 'type': exp['type'], 'storagetype': exp['storagetype'], 'machineId': exp[
                                'machineId'], 'id': exp['id'], 'name': exp['name'], 'timestamp': exp['timestamp']})
        return exportresult

    @auth(['level1', 'level2', 'level3'])
    def tag(self, machineId, tagName, **kwargs):
        """
        Adds a tag to a machine, useful for indexing and following a (set of) machines
        param:machineId id of the machine to tag
        param:tagName tag
        """
        vmachine = self._validateMachineRequest(machineId)
        tags = j.core.tags.getObject(vmachine.tags)
        if tags.labelExists(tagName):
            raise exceptions.Conflict('Tag %s is already assigned to this vMachine' % tagName)

        tags.labelSet(tagName)
        vmachine.tags = tags.tagstring
        self.models.vmachine.set(vmachine)
        return True

    @auth(['level1', 'level2', 'level3'])
    def untag(self, machineId, tagName, **kwargs):
        """
        Removes a specific tag from a machine
        param:machineId id of the machine to untag
        param:tagName tag
        """
        vmachine = self._validateMachineRequest(machineId)
        tags = j.core.tags.getObject(vmachine.tags)
        if not tags.labelExists(tagName):
            raise exceptions.NotFound('vMachine does not have tag %s' % tagName)

        tags.labelDelete(tagName)
        vmachine.tags = tags.tagstring
        self.models.vmachine.set(vmachine)
        return True

    @auth(['level1', 'level2', 'level3'])
    def list(self, tag=None, computeNode=None, accountName=None, cloudspaceId=None, **kwargs):
        """
        List the undestroyed machines based on specific criteria
        At least one of the criteria needs to be passed
        param:tag a specific tag
        param:computenode name of a specific computenode
        param:accountname specific account
        param:cloudspaceId specific cloudspace
        """
        if not tag and not computeNode and not accountName and not cloudspaceId:
            raise exceptions.BadRequest('At least one parameter must be passed')
        query = dict()
        if tag:
            query['tags'] = tag
        if computeNode:
            stacks = self.models.stack.search({'referenceId': computeNode})[1:]
            if stacks:
                stack_id = stacks[0]['id']
                query['stackId'] = stack_id
            else:
                return list()
        if accountName:
            accounts = self.models.account.search({'name': accountName})[1:]
            if accounts:
                account_id = accounts[0]['id']
                cloudspaces = self.models.cloudspace.search({'accountId': account_id})[1:]
                if cloudspaces:
                    cloudspaces_ids = [cs['id'] for cs in cloudspaces]
                    query['cloudspaceId'] = {'$in': cloudspaces_ids}
                else:
                    return list()
            else:
                return list()
        if cloudspaceId:
            query['cloudspaceId'] = cloudspaceId

        query['status'] = {'$ne': 'destroyed'}
        return self.models.vmachine.search(query)[1:]

    @auth(['level1', 'level2', 'level3'])
    def checkImageChain(self, machineId, **kwargs):
        """
        Checks on the computenode the vm is on if the vm image is there
        Check the chain of the vmimage to see if parents are there (the template starting from)
        (executes the vm.hdcheck jumpscript)
        param:machineId id of the machine
        result dict,,
        """
        # put your code here to implement this method
        vmachine = self.models.vmachine.get(int(machineId))
        stack = self.models.stack.get(vmachine.stackId)
        job = self.acl.executeJumpscript('cloudscalers', 'vm_livemigrate_getdisksinfo', args={
                                         'vmId': vmachine.id, 'chain': True}, gid=stack.gid, nid=int(stack.referenceId), wait=True)
        if job['state'] != 'OK':
            raise exceptions.Error('Something wrong with image or node see job %s' % job['guid'])
        return job['result']

    @auth(['level1', 'level2', 'level3'])
    def stopForAbusiveResourceUsage(self, accountId, machineId, reason, **kwargs):
        '''If a machine is abusing the system and violating the usage policies it can be stopped using this procedure.
        A ticket will be created for follow up and visibility, the machine stopped, the image put on slower storage and the ticket is automatically closed if all went well.
        Use with caution!
        @param:accountId int,,Account ID, extra validation for preventing a wrong machineId
        @param:machineId int,,Id of the machine
        @param:reason str,,Reason
        '''
        machineId = int(machineId)
        vmachine = self._validateMachineRequest(machineId)

        stack = self.models.stack.get(vmachine.stackId)
        subject = 'Stopping vmachine "%s" for abusive resources usage' % vmachine.name
        msg = 'Account: %s\nMachine: %s\nReason: %s' % (accountId, vmachine.name, reason)
#        ticketId =self.whmcs.tickets.create_ticket(subject, msg, "High")
        args = {'machineId': vmachine.id, 'nodeId': vmachine.referenceId}
        self.acl.executeJumpscript(
            'cloudscalers', 'vm_stop_for_abusive_usage', gid=stack.gid, nid=stack.referenceId, args=args, wait=False)
#        self.whmcs.tickets.close_ticket(ticketId)

    @auth(['level1', 'level2', 'level3'])
    def backupAndDestroy(self, accountId, machineId, reason, **kwargs):
        """
        * Create a ticketjob
        * Call the backup method
        * Destroy the machine
        * Close the ticket
        """
        vmachine = self._validateMachineRequest(machineId)
        stack = self.models.stack.get(vmachine.stackId)
        args = {'accountId': accountId, 'machineId': machineId, 'reason': reason,
                'vmachineName': vmachine.name, 'cloudspaceId': vmachine.cloudspaceId}
        self.acl.executeJumpscript(
            'cloudscalers', 'vm_backup_destroy', gid=j.application.whoAmI.gid, nid=j.application.whoAmI.nid, args=args, wait=False)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def listSnapshots(self, machineId, **kwargs):
        self._validateMachineRequest(machineId)
        return self.actors.machines.listSnapshots(machineId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def getHistory(self, machineId, **kwargs):
        self._validateMachineRequest(machineId)
        return self.actors.machines.getHistory(machineId)

    @auth(['level1', 'level2', 'level3'])
    def listPortForwards(self, machineId, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        vfwkey = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        results = list()
        machineips = [nic.ipAddress for nic in vmachine.nics if not nic.ipAddress == 'Undefined']
        if self.vfwcl.virtualfirewall.exists(vfwkey):
            vfw = self.vfwcl.virtualfirewall.get(vfwkey).dump()
            for idx, forward in enumerate(vfw['tcpForwardRules']):
                if forward['toAddr'] in machineips:
                    forward['id'] = idx
                    results.append(forward)
        return results

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def createPortForward(self, machineId, localPort, destPort, proto, reason, **kwargs):
        machineId = int(machineId)
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        self.actors.portforwarding.create(
            cloudspace.id, cloudspace.publicipaddress, str(destPort), vmachine.id, str(localPort), proto)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def deletePortForward(self, machineId, publicIp, publicPort, proto, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        self.actors.portforwarding.deleteByPort(cloudspace.id, publicIp, publicPort, proto)


    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def addDisk(self, machineId, diskName, description, size=10, **kwargs):
        self._validateMachineRequest(machineId)
        self.actors.machines.addDisk(machineId, diskName, description, size=size, type='D')

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def deleteDisk(self, machineId, diskId, **kwargs):
        self._validateMachineRequest(machineId)
        return self.actors.disks.delete(diskId=diskId, detach=True)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def createTemplate(self, machineId, templateName, reason, **kwargs):
        self._validateMachineRequest(machineId)
        self.actors.machines.createTemplate(machineId, templateName, None)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def updateMachine(self, machineId, description, reason, **kwargs):
        vmachine = self._validateMachineRequest(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        account = self.models.account.get(cloudspace.accountId)
        msg = 'Account: %s\nSpace: %s\nMachine: %s\nUpdating machine description: %s\nReason: %s' % (vmachine.name, description, reason)
        subject = 'Updating description: %s for machine %s' % (description, vmachine.name)
#        ticketId =self.whmcs.tickets.create_ticket(subject, msg, 'High')
        self.actors.machines.update(machineId, description=description)
#        self.whmcs.tickets.close_ticket(ticketId)

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def attachPublicNetwork(self, machineId, **kwargs):
        return self.actors.machines.attachPublicNetwork(machineId)
    
    
    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def detachPublicNetwork(self, machineId, **kwargs):
        return self.actors.machines.detachPublicNetwork(machineId)
    