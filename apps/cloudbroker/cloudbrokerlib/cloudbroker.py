from JumpScale import j
from libcloud.compute.types import Provider
from libcloud.compute.providers import get_driver
from libcloud.compute.base import NodeAuthPassword
from JumpScale.portal.portal import exceptions
from CloudscalerLibcloud.compute.drivers.libvirt_driver import CSLibvirtNodeDriver
from CloudscalerLibcloud.compute.drivers.openstack_driver import OpenStackNodeDriver
from cloudbrokerlib import enums
from CloudscalerLibcloud.utils.connection import CloudBrokerConnection
import random
import time
import string
import re

ujson = j.db.serializers.ujson
models = j.clients.osis.getNamespace('cloudbroker')

def removeConfusingChars(input):
    return input.replace('0', '').replace('O', '').replace('l', '').replace('I', '')

class Dummy(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)


class CloudProvider(object):
    _providers = dict()

    def __init__(self, stackId):
        if stackId not in CloudProvider._providers:
            stack = models.stack.get(stackId)
            providertype = getattr(Provider, stack.type)
            kwargs = dict()
            if stack.type == 'OPENSTACK':
                args = [stack.login, stack.passwd]
                kwargs['ex_force_auth_url'] = stack.apiUrl
                kwargs['ex_force_auth_version'] = '2.0_password'
                kwargs['ex_tenant_name'] = stack.login
                driver = OpenStackNodeDriver(*args, **kwargs)
                CloudProvider._providers[stackId] = driver
            if stack.type == 'DUMMY':
                DriverClass = get_driver(providertype)
                args = [1, ]
                CloudProvider._providers[stackId] = DriverClass(*args, **kwargs)
            if stack.type == 'LIBVIRT':
                kwargs['id'] = stack.referenceId
                kwargs['uri'] = stack.apiUrl
                kwargs['gid'] = stack.gid
                driver = CSLibvirtNodeDriver(**kwargs)
                client = None
                if 'libcloud__libvirt' not in j.apps.system.contentmanager.getActors():
                    client = j.clients.portal.getByInstance('cloudbroker')
                cb = CloudBrokerConnection(client)
                driver.set_backend(cb)
                CloudProvider._providers[stackId] = driver

        self.client = CloudProvider._providers[stackId]
        self.stackId = stackId

    def getSize(self, brokersize, firstdisk):
        providersizes = self.client.list_sizes()
        for s in providersizes:
            if s.ram == brokersize.memory and firstdisk.sizeMax == s.disk and s.extra['vcpus'] == brokersize.vcpus:
                return s
        return None

    def getImage(self, imageId):
        iimage = models.image.get(imageId)
        for image in self.client.ex_list_images():
            if image.id == iimage.referenceId:
                return image, image
        return None, None


class CloudBroker(object):
    _resourceProviderId2StackId = dict()

    def __init__(self):
        self.Dummy = Dummy
        self._actors = None
        self.machine = Machine(self)
        self.syscl = j.clients.osis.getNamespace('system')
        self.cbcl = j.clients.osis.getNamespace('cloudbroker')

    @property
    def actors(self):
        if not self._actors:
            cl = j.clients.portal.getByInstance('cloudbroker')
            self._actors = cl.actors
        return self._actors

    def getProviderByStackId(self, stackId):
        return CloudProvider(stackId)

    def addDiskToMachine(self, machine, disk):
        return True

    def getProviderByGID(self, gid):
        stacks = models.stack.search({'gid': gid, 'status': 'ENABLED'})[1:]
        if stacks:
            return self.getProviderByStackId(stacks[0]['id'])
        raise exceptions.ServiceUnavailable('Not enough resources available on current location')

    def markProvider(self, stackId, eco):
        stack = models.stack.get(stackId)
        stack.error += 1
        if stack.error >= 2:
            stack.status = 'ERROR'
            stack.eco = eco.guid
        models.stack.set(stack)

    def clearProvider(self, stackId):
        stack = models.stack.get(stackId)
        stack.error = 0
        stack.eco = None
        stack.status = 'ENABLED'
        models.stack.set(stack)

    def getIdByReferenceId(self, objname, referenceId):
        model = getattr(models, '%s' % objname)
        queryapi = getattr(model, 'search')
        query = {'referenceId': referenceId}
        ids = queryapi(query)[1:]
        if ids:
            return ids[0]['id']
        else:
            return None

    def getBestProvider(self, gid, imageId, excludelist=[]):
        capacityinfo = self.getCapacityInfo(gid, imageId)
        if not capacityinfo:
            return -1
        capacityinfo = [node for node in capacityinfo if node['id'] not in excludelist]
        if not capacityinfo:
            return -1

        provider = capacityinfo[0] # is sorted by least used
        return provider

    def chooseProvider(self, machine):
        cloudspace = models.cloudspace.get(machine.cloudspaceId)
        newstack = self.getBestProvider(cloudspace.gid, machine.imageId)
        if newstack == -1:
            raise exceptions.ServiceUnavailable('Not enough resources available to start the requested machine')
        machine.stackId = newstack['id']
        models.vmachine.set(machine)
        return True

    def getCapacityInfo(self, gid, imageId):
        resourcesdata = list()
        activesessions = []
        for gidnid, session in j.clients.agentcontroller.get().listSessions().iteritems():
            # skip nodes that didnt respond in last 60 seconds
            if session[0] < time.time() - 60:
                continue
            gridid, nid = gidnid.split('_')
            gridid, nid = int(gridid), int(nid)
            activesessions.append((gridid, nid))

        stacks = models.stack.search({"images": imageId, 'gid': gid})[1:]
        sizes = {s['id']: s['memory'] for s in models.size.search({'$fields': ['id', 'memory']})[1:]}
        for stack in stacks:
            if stack.get('status', 'ENABLED') == 'ENABLED':
                nodekey = (stack['gid'], int(stack['referenceId']))
                if nodekey not in activesessions:
                    continue

                # search for all vms running on the stacks
                usedvms = models.vmachine.search({'$fields': ['id', 'sizeId'],
                                                  '$query': {'stackId': stack['id'],
                                                             'status': {'$nin': ['HALTED', 'ERROR', 'DESTROYED']}}
                                                  }
                                                 )[1:]
                if usedvms:
                    stack['usedmemory'] = sum(sizes[vm['sizeId']] for vm in usedvms)
                else:
                    stack['usedmemory'] = 0
                resourcesdata.append(stack)
        resourcesdata.sort(key=lambda s: s['usedmemory'])
        return resourcesdata

    def stackImportSizes(self, stackId):
        """
        Import disk sizes from a provider

        :param      stackId: Stack ID
        :type       id: ``int``

        :rtype: ``int``
        """
        provider = CloudProvider(stackId)
        if not provider:
            raise RuntimeError('Provider not found')

        stack = models.stack.get(stackId)
        gridId = stack.gid
        cb_sizes = models.size.search({})[1:]  # cloudbroker sizes
        psizes = {}  # provider sizes

        # provider sizes formated as {(memory, cpu):[disks]}. i.e {(2048, 2):[10, 20, 30]}
        for s in provider.client.list_sizes():
            md = (s.ram, s.extra['vcpus'])
            psizes[md] = psizes.get(md, []) + [s.disk]

        for cb_size in cb_sizes:
            record = (cb_size['memory'], cb_size['vcpus'])
            if record not in psizes:  # obsolete sizes
                if gridId in cb_size['gids']:
                    cb_size['gids'].remove(gridId)  # remove gid from obsolete size
                    if not cb_size['gids']:
                        models.size.delete(cb_size['id'])  # delete obsolete size if having no gids
                    else:
                        models.size.set(cb_size)  # update obsolete size [Save without the gridId of the stack]
            else:
                # Update existing sizes (disks and gids)
                if set(cb_size['disks']) == set(psizes[record]):
                    if gridId not in cb_size['gids']:
                        cb_size['gids'].append(gridId)
                        models.size.set(cb_size)
                    psizes.pop(record)  # remove from dict
        # add new
        for k, v in psizes.iteritems():
            s = models.size.new()
            s.memory = k[0]
            s.vcpus = k[1]
            s.gids = [gridId]
            s.disks = v
            models.size.set(s)

        # Return length of newly added sizes
        return len(psizes)

    def stackImportImages(self, stackId):
        """
        Sync Provider images [Deletes obsolete images that are deleted from provider side/Add new ones]
        """
        provider = CloudProvider(stackId)
        if not provider:
            raise RuntimeError('Provider not found')

        pname = provider.client.name.lower()
        stack = models.stack.get(stackId)
        stack.images = list()

        pimages = {}
        for p in provider.client.ex_list_images():
            pimages[p.id] = p
        pimages_ids = set(pimages.keys())

        images_current = models.image.search({'provider_name': pname})[1:]
        images_current_ids = set([p['referenceId'] for p in images_current])

        new_images_ids = pimages_ids - images_current_ids
        updated_images_ids = pimages_ids & images_current_ids

        # Add new Images
        for id in new_images_ids:
            pimage = pimages[id]
            image = models.image.new()
            image.provider_name = pname
            image.name = pimage.name
            image.referenceId = pimage.id
            image.type = pimage.extra.get('imagetype', 'Unknown')
            image.size = pimage.extra.get('size', 0)
            image.username = pimage.extra.get('username', 'cloudscalers')
            image.status = getattr(pimage, 'status', 'CREATED') or 'CREATED'
            image.accountId = 0

            imageid = models.image.set(image)[0]
            stack.images.append(imageid)

        # Update current images
        for image in models.image.search({'referenceId': {'$in': list(updated_images_ids)}})[1:]:
            pimage = pimages[image['referenceId']]
            image['name'] = pimage.name
            image['type'] = pimage.extra.get('imagetype', 'Unknown')
            image['size'] = pimage.extra.get('size', 0)
            image['username'] = pimage.extra.get('username', 'cloudscalers')
            image['status'] = getattr(pimage, 'status', 'CREATED') or 'CREATED'
            image['provider_name'] = pname

            imageid = models.image.set(image)[0]
            stack.images.append(imageid)

        models.stack.set(stack)
        return len(new_images_ids)

    def checkUser(self, username, activeonly=True):
        """
        Check if a user exists with the given username or email address

        :param username: username or emailaddress of the user
        :param activeonly: only return activated users if set to True
        :return: User if found
        """
        query = {'$or': [{'id': username}, {'emails': username}]}
        if activeonly:
            query['active'] = True
        users = self.syscl.user.search(query)[1:]
        if users:
            return users[0]
        else:
            return None

    def updateResourceInvitations(self, username, emailaddress):
        """
        Update the invitations in ACLs of Accounts, Cloudspaces and Machines after user registration

        :param username: username the user has registered with
        :param emailaddress: emailaddress of the registered users
        :return: True if resources were updated
        """
        # Validate that only one email address was sent for updating the resources
        if len(emailaddress.split(',')) > 1:
            raise exceptions.BadRequest('Cannot update resource invitations for a list of multiple '
                                        'email addresses')

        for account in self.cbcl.account.search({'acl.userGroupId': emailaddress})[1:]:
            accountobj = self.cbcl.account.get(account['guid'])
            for ace in accountobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = 'CONFIRMED'
                    self.cbcl.account.set(accountobj)
                    break

        for cloudspace in self.cbcl.cloudspace.search({'acl.userGroupId': emailaddress})[1:]:
            cloudspaceobj = self.cbcl.cloudspace.get(cloudspace['guid'])
            for ace in cloudspaceobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = 'CONFIRMED'
                    self.cbcl.cloudspace.set(cloudspaceobj)
                    break

        for vmachine in self.cbcl.vmachine.search({'acl.userGroupId': emailaddress})[1:]:
            vmachineobj = self.cbcl.vmachine.get(vmachine['guid'])
            for ace in cloudspaceobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = 'CONFIRMED'
                    self.cbcl.vmachine.set(vmachineobj)
                    break

        return True

    def isaccountuserdeletable(self, userace, acl):
        if set(userace.right) != set('ARCXDU'):
            return True
        else:
            otheradmins = filter(lambda a: set(a.right) == set('ARCXDU') and a != userace, acl)
            if not otheradmins:
                return False
            else:
                return True

    def isValidEmailAddress(self, emailaddress):
        r = re.compile('^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}$')
        return r.match(emailaddress) is not None

    def isValidRole(self, accessrights):
        """
        Validate that the accessrights map to a valid access role on a resource
        'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin

        :param accessrights: string with the accessrights to verify
        :return: role name if a valid set of permissions, otherwise fail with an exception
        """
        if accessrights == 'R':
            return 'Read'
        elif set(accessrights) == set('RCX'):
            return 'Read/Write'
        elif set(accessrights) == set('ARCXDU'):
            return 'Admin'
        else:
            raise exceptions.BadRequest('Invalid set of access rights "%s". Please only use "R" '
                                        'for Read, "RCX" for Read/Write and "ARCXDU" for Admin '
                                        'access.' % accessrights)


class Machine(object):
    def __init__(self, cb):
        self.cb = cb
        self.acl = j.clients.agentcontroller.get()

    def cleanup(self, machine):
        for diskid in machine.disks:
            models.disk.delete(diskid)
        models.vmachine.delete(machine.id)

    def validateCreate(self, cloudspace, name, sizeId, imageId, disksize, minimum_days_of_credit_required):
        if not self._assertName(cloudspace.id, name):
            raise exceptions.Conflict('Selected name already exists')
        if not disksize:
            raise exceptions.BadRequest("Invalid disksize %s" % disksize)

        if cloudspace.status == 'DESTROYED':
            raise exceptions.BadRequest('Can not create machine on destroyed Cloud Space')

        image = models.image.get(imageId)
        if disksize < image.size:
            raise exceptions.BadRequest("Disk size of {}GB is to small for image {}, which requires at least {}GB.".format(disksize, image.name, image.size))

        sizeId = int(sizeId)
        imageId = int(imageId)
        #Check if there is enough credit
        accountId = cloudspace.accountId

    def _assertName(self, cloudspaceId, name, **kwargs):
        results = models.vmachine.search({'cloudspaceId': cloudspaceId, 'name': name, 'status': {'$nin': ['DESTROYED', 'ERROR']}})[1:]
        return False if results else True

    def createModel(self, name, description, cloudspace, imageId, sizeId, disksize, datadisks):
        datadisks = datadisks or []

        #create a public ip and virtual firewall on the cloudspace if needed
        if cloudspace.status != 'DEPLOYED':
            args = {'cloudspaceId': cloudspace.id}
            self.acl.executeJumpscript('cloudscalers', 'cloudbroker_deploycloudspace', args=args, nid=j.application.whoAmI.nid, wait=False)

        image = models.image.get(imageId)
        machine = models.vmachine.new()
        machine.cloudspaceId = cloudspace.id
        machine.descr = description
        machine.name = name
        machine.sizeId = sizeId
        machine.imageId = imageId
        machine.creationTime = int(time.time())

        def addDisk(order, size, type, name=None):
            disk = models.disk.new()
            disk.name = name or 'Disk nr %s' % order
            disk.descr = 'Machine disk of type %s' % type
            disk.sizeMax = size
            disk.accountId = cloudspace.accountId
            disk.gid = cloudspace.gid
            disk.order = order
            disk.type = type
            diskid = models.disk.set(disk)[0]
            machine.disks.append(diskid)
            return diskid

        addDisk(-1, disksize, 'B', 'Boot disk')
        diskinfo = []
        for order, datadisksize in enumerate(datadisks):
            diskid = addDisk(order, int(datadisksize), 'D')
            diskinfo.append((diskid, int(datadisksize)))

        account = machine.new_account()
        if image.type == 'Custom Templates':
            account.login = 'Custom login'
            account.password = 'Custom password'
        else:
            if hasattr(image, 'username') and image.username:
                account.login = image.username
            else:
                account.login = 'cloudscalers'
            length = 6
            chars = removeConfusingChars(string.letters + string.digits)
            letters = [removeConfusingChars(string.ascii_lowercase), removeConfusingChars(string.ascii_uppercase)]
            passwd = ''.join(random.choice(chars) for _ in xrange(length))
            passwd = passwd + random.choice(string.digits) + random.choice(letters[0]) + random.choice(letters[1])
            account.password = passwd
        auth = NodeAuthPassword(account.password)
        machine.id = models.vmachine.set(machine)[0]
        return machine, auth, diskinfo

    def updateMachineFromNode(self, machine, node, stackId, psize):
        machine.referenceId = node.id
        machine.referenceSizeId = psize.id
        machine.stackId = stackId
        machine.status = enums.MachineStatus.RUNNING
        machine.hostName = node.name
        if 'ifaces' in node.extra:
            for iface in node.extra['ifaces']:
                for nic in machine.nics:
                    if nic.macaddress == iface.mac:
                        break
                else:
                    nic = machine.new_nic()
                    nic.macAddress = iface.mac
                    nic.deviceName = iface.target
                    nic.type = iface.type
                    nic.ipAddress = 'Undefined'
        else:
            for ipaddress in node.public_ips:
                nic = machine.new_nic()
                nic.ipAddress = ipaddress
        models.vmachine.set(machine)

        for order, diskid in enumerate(machine.disks):
            disk = models.disk.get(diskid)
            disk.stackId = stackId
            disk.referenceId = node.extra['volumes'][order].id
            models.disk.set(disk)

    def create(self, machine, auth, cloudspace, diskinfo, imageId, stackId):
        excludelist = []
        name = 'vm-%s' % machine.id
        newstackId = stackId

        def getStackAndProvider(newstackId):
            try:
                if not newstackId:
                    stack = self.cb.getBestProvider(cloudspace.gid, imageId, excludelist)
                    if stack == -1:
                        self.cleanup(machine)
                        raise exceptions.ServiceUnavailable('Not enough resources available to provision the requested machine')
                    newstackId = stack['id']
                provider = self.cb.getProviderByStackId(newstackId)
            except:
                self.cleanup(machine)
                raise
            return provider, newstackId

        node = -1
        while node == -1:
            provider, newstackId = getStackAndProvider(newstackId)
            image, pimage = provider.getImage(machine.imageId)
            psize = self.getSize(provider, machine)
            machine.cpus = psize.vcpus if hasattr(psize, 'vcpus') else None
            try:
                node = provider.client.create_node(name=name, image=pimage, size=psize, auth=auth, networkid=cloudspace.networkId, datadisks=diskinfo)
            except Exception as e:
                eco = j.errorconditionhandler.processPythonExceptionObject(e)
                self.cb.markProvider(newstackId, eco)
                newstackId = 0
                machine.status = 'ERROR'
                models.vmachine.set(machine)
            if node == -1 and stackId:
                raise exceptions.ServiceUnavailable('Not enough resources available to provision the requested machine')
        self.cb.clearProvider(newstackId)
        self.updateMachineFromNode(machine, node, newstackId, psize)
        tags = str(machine.id)
        j.logger.log('Created', category='machine.history.ui', tags=tags)
        return machine.id


    def getSize(self, provider, machine):
        brokersize = models.size.get(machine.sizeId)
        firstdisk = models.disk.get(machine.disks[0])
        return provider.getSize(brokersize, firstdisk)
