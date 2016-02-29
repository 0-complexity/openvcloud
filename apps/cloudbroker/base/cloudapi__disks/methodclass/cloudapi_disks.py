from JumpScale import j
from JumpScale.portal.portal.auth import auth as audit
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import authenticator
from cloudbrokerlib.baseactor import BaseActor
from libcloud.compute.base import StorageVolume
from billingenginelib import pricing
from billingenginelib import account as accountbilling


class cloudapi_disks(BaseActor):
    """
    API Actor api, this actor is the final api a enduser uses to manage his resources

    """
    def __init__(self):
        super(cloudapi_disks, self).__init__()
        self.osisclient = j.core.portal.active.osis
        self.acl = j.clients.agentcontroller.get()
        self.osis_logs = j.clients.osis.getCategory(self.osisclient, "system", "log")
        self._pricing = pricing.pricing()
        self._accountbilling = accountbilling.account()
        self._minimum_days_of_credit_required = float(self.hrd.get("instance.openvcloud.cloudbroker.creditcheck.daysofcreditrequired"))
        self.netmgr = j.apps.jumpscale.netmgr

    def getStorageVolume(self, disk, provider, node=None):
        if not isinstance(disk, dict):
            disk = disk.dump()
        return StorageVolume(id=disk['referenceId'], name=disk['name'], size=disk['sizeMax'], driver=provider.client, extra={'node': node})

    @authenticator.auth(acl={'account': set('C')})
    @audit()
    def create(self, accountId, gid, name, description, size=10, type='D', **kwargs):
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
        # Validate that enough resources are available in the account CU limits to add the disk
        j.apps.cloudapi.accounts.checkAvailableMachineResources(accountId, vdisksize=size)
        disk, volume = self._create(accountId, gid, name, description, size, type)
        return disk.id

    def _create(self, accountId, gid, name, description, size=10, type='D', **kwargs):
        if size > 2000:
            raise exceptions.BadRequest("Disk size can not be bigger than 2000 GB")
        disk = self.models.disk.new()
        disk.name = name
        disk.descr = description
        disk.sizeMax = size
        disk.type = type
        disk.gid = gid
        disk.accountId = accountId
        diskid = self.models.disk.set(disk)[0]
        disk = self.models.disk.get(diskid)
        try:
            provider = self.cb.getProviderByGID(gid)
            volume = provider.client.create_volume(disk.sizeMax, disk.id)
            disk.referenceId = volume.id
        except:
            self.models.disk.delete(disk.id)
            raise
        self.models.disk.set(disk)
        return disk, volume

    @authenticator.auth(acl={'account': set('R')})
    @audit()
    def get(self, diskId, **kwargs):
        """
        Get disk details

        :param diskId: id of the disk
        :return: dict with the disk details
        """
        if not self.models.disk.exists(diskId):
            raise exceptions.NotFound('Can not find disk with id %s' % diskId)
        return self.models.disk.get(diskId).dump()

    @authenticator.auth(acl={'account': set('R')})
    @audit()
    def list(self, accountId, type, **kwargs):
        """
        List the created disks belonging to an account

        :param accountId: id of accountId the disks belongs to
        :param type: type of type of the disks
        :return: list with every element containing details of a disk as a dict
        """
        query = {'accountId': accountId}
        if type:
            query['type'] = type
        return self.models.disk.search(query)[1:]

    @authenticator.auth(acl={'cloudspace': set('X')})
    @audit()
    def delete(self, diskId, detach, **kwargs):
        """
        Delete a disk

        :param diskId: id of disk to delete
        :param detach: detach disk from machine first
        :return True if disk was deleted successfully
        """
        if not self.models.disk.exists(diskId):
            return True
        disk = self.models.disk.get(diskId)
        if disk.status == 'DESTROYED':
            return True
        machines = self.models.vmachine.search({'disks': diskId, 'status': {'$ne': 'DESTROYED'}})[1:]
        if machines and not detach:
            raise exceptions.Conflict('Can not delete disk which is attached')
        elif machines:
            j.apps.cloudapi.machines.detachDisk(machineId=machines[0]['id'], diskId=diskId, **kwargs)
        provider = self.cb.getProviderByGID(disk.gid)
        volume = self.getStorageVolume(disk, provider)
        provider.client.destroy_volume(volume)
        disk.status = 'DESTROYED'
        self.models.disk.set(disk)
        return True
