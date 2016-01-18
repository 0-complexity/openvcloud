from JumpScale import j
from JumpScale.portal.portal.auth import auth as audit
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import authenticator, network
from billingenginelib import account as accountbilling
from billingenginelib import pricing
from cloudbrokerlib.baseactor import BaseActor
import netaddr
import uuid
import time


def getIP(network):
    if not network:
        return network
    return str(netaddr.IPNetwork(network).ip)


class cloudapi_cloudspaces(BaseActor):
    """
    API Actor api for managing cloudspaces, this actor is the final api a enduser uses to manage cloudspaces

    """
    def __init__(self):
        super(cloudapi_cloudspaces, self).__init__()
        self.libvirt_actor = j.apps.libcloud.libvirt
        self.netmgr = j.apps.jumpscale.netmgr
        self.network = network.Network(self.models)
        self._accountbilling = accountbilling.account()
        self._pricing = pricing.pricing()
        self._minimum_days_of_credit_required = float(self.hrd.get("instance.openvcloud.cloudbroker.creditcheck.daysofcreditrequired"))
        self.systemodel = j.clients.osis.getNamespace('system')

    @authenticator.auth(acl={'cloudspace': set('U')})
    @audit()
    def addUser(self, cloudspaceId, userId, accesstype, **kwargs):
        """
        Give a registered user access rights

        :param cloudspaceId: id of the cloudspace
        :param userId: username or emailaddress of the user to grant access
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user was added successfully
        """
        user = self.cb.checkUser(userId)
        if not user:
            raise exceptions.NotFound("User is not registered on the system")
        else:
            # Replace email address with ID
            userId = user['id']

        return self._addACE(cloudspaceId, userId, accesstype, userstatus='CONFIRMED')

    @authenticator.auth(acl={'cloudspace': set('U')})
    @audit()
    def addExternalUser(self, cloudspaceId, emailaddress, accesstype, **kwargs):
        """
        Give an unregistered user access rights by sending an invite email

        :param cloudspaceId: id of the cloudspace
        :param emailaddress: emailaddress of the unregistered user that will be invited
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user was added successfully
        """
        if self.systemodel.user.search({'emails': emailaddress})[1:]:
            raise exceptions.BadRequest('User is already registered on the system, please add as '
                                        'a normal user')

        self._addACE(cloudspaceId, emailaddress, accesstype, userstatus='INVITED')
        try:
            j.apps.cloudapi.users.sendInviteLink(emailaddress, 'cloudspace', cloudspaceId,
                                                 accesstype)
            return True
        except:
            self.deleteUser(cloudspaceId, emailaddress, recursivedelete=False)
            raise

    def _addACE(self, cloudspaceId, userId, accesstype, userstatus='CONFIRMED'):
        """
        Add a new ACE to the ACL of the cloudspace

        :param cloudspaceId: id of the cloudspace
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :param userstatus: status of the user (CONFIRMED or INVITED)
        :return True if ACE was added successfully
        """
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        cloudspace_acl = authenticator.auth().getCloudspaceAcl(cloudspaceId)
        if userId in cloudspace_acl:
            return self._updateACE(cloudspaceId, userId, accesstype, userstatus)

        ace = cloudspace.new_acl()
        ace.userGroupId = userId
        ace.type = 'U'
        ace.right = accesstype
        ace.status = userstatus
        self.models.cloudspace.set(cloudspace)
        return True

    def _updateACE(self, cloudspaceId, userId, accesstype, userstatus):
        """
        Update an existing ACE in the ACL of a cloudspace

        :param cloudspaceId: id of the cloudspace
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :param userstatus: status of the user (CONFIRMED or INVITED)
        :return True if ACE was successfully updated, False if no update is needed
        """
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        cloudspace_acl = authenticator.auth().getCloudspaceAcl(cloudspaceId)
        if userId in cloudspace_acl:
            useracl = cloudspace_acl[userId]
        else:
            raise exceptions.NotFound('User does not have any access rights to update')

        if 'account_right' in useracl and set(accesstype) == set(useracl['account_right']):
            # No need to add any access rights as same rights are inherited
            # Remove cloudspace level access rights if present
            for ace in cloudspace.acl:
                if ace.userGroupId == userId and ace.type == 'U':
                    cloudspace.acl.remove(ace)
                    self.models.cloudspace.set(cloudspace)
                    break
            return False
        # If user has higher access rights on owning account level, then do not update
        elif 'account_right' in useracl and set(accesstype).issubset(set(useracl['account_right'])):
            raise exceptions.Conflict('User already has a higher access level to owning account')
        else:
            # grant higher access level
            for ace in cloudspace.acl:
                if ace.userGroupId == userId and ace.type == 'U':
                    ace.right = accesstype
                    break
            else:
                ace = cloudspace.new_acl()
                ace.userGroupId = userId
                ace.type = 'U'
                ace.right = accesstype
                ace.status = userstatus
            self.models.cloudspace.set(cloudspace)
        return True


    @authenticator.auth(acl={'cloudspace': set('U')})
    @audit()
    def updateUser(self, cloudspaceId, userId, accesstype, **kwargs):
        """
        Update user access rights

        :param cloudspaceId: id of the cloudspace
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user access was updated successfully
        """
        # Check if user exists in the system or is an unregistered invited user
        existinguser = self.systemodel.user.search({'id': userId})[1:]
        if existinguser:
            userstatus = 'CONFIRMED'
        else:
            userstatus = 'INVITED'
        return self._updateACE(cloudspaceId, userId, accesstype, userstatus)

    def _listActiveCloudSpaces(self, accountId):
        account = self.models.account.get(accountId)
        if account.status == 'DISABLED':
            return []
        query = {'accountId': accountId, 'status': {'$ne': 'DESTROYED'}}
        results = self.models.cloudspace.search(query)[1:]
        return results

    @authenticator.auth(acl={'account': set('C')})
    @audit()
    def create(self, accountId, location, name, access, maxMemoryCapacity, maxDiskCapacity,
               **kwargs):
        """
        Create an extra cloudspace

        :param accountId: id of acount this cloudspace belongs to
        :param location: name of location
        :param name: name of cloudspace to create
        :param access: username of a user which has full access to this space
        :param maxMemoryCapacity: max size of memory in space (in GB)
        :param maxDiskCapacity: max size of aggregated disks (in GB)
        :return int with id of created cloudspace
        """
        accountId = int(accountId)
        locations = self.models.location.search({'locationCode': location})[1:]
        if not locations:
            raise exceptions.BadRequest('Location %s does not exists' % location)
        location = locations[0]

        active_cloudspaces = self._listActiveCloudSpaces(accountId)
        # Extra cloudspaces require a payment and a credit check
        if (len(active_cloudspaces) > 0):
            if (not self._accountbilling.isPayingCustomer(accountId)):
                raise exceptions.Conflict('Creating an extra cloudspace is only available if you made at least 1 payment')

            available_credit = self._accountbilling.getCreditBalance(accountId)
            burnrate = self._pricing.get_burn_rate(accountId)['hourlyCost']
            new_burnrate = burnrate + self._pricing.get_cloudspace_price_per_hour()
            if available_credit < (new_burnrate * 24 * self._minimum_days_of_credit_required):
                raise exceptions.Conflict('Not enough credit to hold this cloudspace for %i days' % self._minimum_days_of_credit_required)

        cs = self.models.cloudspace.new()
        cs.name = name
        cs.accountId = accountId
        cs.location = location['locationCode']
        cs.gid = location['gid']
        ace = cs.new_acl()
        ace.userGroupId = access
        ace.type = 'U'
        ace.right = 'CXDRAU'
        ace.status = 'CONFIRMED'
        cs.resourceLimits['CU'] = maxMemoryCapacity
        cs.resourceLimits['SU'] = maxDiskCapacity
        cs.status = 'VIRTUAL'
        networkid = self.libvirt_actor.getFreeNetworkId(cs.gid)
        if not networkid:
            raise RuntimeError("Failed to get networkid")

        cs.networkId = networkid
        cs.secret = str(uuid.uuid4())
        cs.creationTime = int(time.time())
        cloudspace_id = self.models.cloudspace.set(cs)[0]
        return cloudspace_id

    def _release_resources(self, cloudspace):
         #delete routeros
        fws = self.netmgr.fw_list(cloudspace.gid, str(cloudspace.id))
        if fws:
            self.netmgr.fw_delete(fws[0]['guid'], cloudspace.gid)
        if cloudspace.networkId:
            self.libvirt_actor.releaseNetworkId(cloudspace.gid, cloudspace.networkId)
        if cloudspace.publicipaddress:
            self.network.releasePublicIpAddress(cloudspace.publicipaddress)
        cloudspace.networkId = None
        cloudspace.publicipaddress = None
        return cloudspace

    @authenticator.auth(acl={'cloudspace': set('X')})
    def deploy(self, cloudspaceId, **kwargs):
        """
        Create VFW for cloudspace

        :param cloudspaceId: id of the cloudspace
        :return: status of deployment
        """
        cs = self.models.cloudspace.get(cloudspaceId)
        if cs.status != 'VIRTUAL':
            return cs.status

        cs.status = 'DEPLOYING'
        self.models.cloudspace.set(cs)
        networkid = cs.networkId
        netinfo = self.network.getPublicIpAddress(cs.gid)
        if netinfo is None:
            cs.status = 'VIRTUAL'
            self.models.cloudspace.set(cs)
            raise RuntimeError("No available public IPAddresses")
        pool, publicipaddress = netinfo
        publicgw = pool.gateway
        network = netaddr.IPNetwork(pool.id)
        publiccidr = network.prefixlen
        if not publicipaddress:
            raise RuntimeError("Failed to get publicip for networkid %s" % networkid)

        cs.publicipaddress = str(publicipaddress)
        self.models.cloudspace.set(cs)
        password = str(uuid.uuid4())
        try:
            self.netmgr.fw_create(cs.gid, str(cloudspaceId), 'admin', password, str(publicipaddress.ip),
                                  'routeros', networkid, publicgwip=publicgw, publiccidr=publiccidr)
        except:
            self.network.releasePublicIpAddress(str(publicipaddress))
            cs.status = 'VIRTUAL'
            self.models.cloudspace.set(cs)
            raise
        cs.status = 'DEPLOYED'
        self.models.cloudspace.set(cs)
        return cs.status

    @authenticator.auth(acl={'cloudspace': set('D')})
    @audit()
    def delete(self, cloudspaceId, **kwargs):
        """
        Delete the cloudspace

        :param cloudspaceId: id of the cloudspace
        :return True if deletion was successful
        """
        cloudspaceId = int(cloudspaceId)
        # A cloudspace may not contain any resources any more
        query = {'cloudspaceId': cloudspaceId, 'status': {'$ne': 'DESTROYED'}}
        results = self.models.vmachine.search(query)[1:]
        if len(results) > 0:
            raise exceptions.Conflict('In order to delete a CloudSpace it can not contain Machines.')
        # The last cloudspace in a space may not be deleted
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        query = {'accountId': cloudspace.accountId,
                  'status': {'$ne': 'DESTROYED'},
                  'id': {'$ne': cloudspaceId}}
        results = self.models.cloudspace.search(query)[1:]
        if len(results) == 0:
            raise exceptions.Conflict('The last CloudSpace of an account can not be deleted.')

        cloudspace.status = "DESTROYING"
        self.models.cloudspace.set(cloudspace)
        cloudspace = self._release_resources(cloudspace)
        cloudspace.status = 'DESTROYED'
        cloudspace.deletionTime = int(time.time())
        self.models.cloudspace.set(cloudspace)
        return True

    @authenticator.auth(acl={'cloudspace': set('R')})
    @audit()
    def get(self, cloudspaceId, **kwargs):
        """
        Get cloudspace details

        :param cloudspaceId: id of the cloudspace
        :return dict with cloudspace details
        """
        cloudspaceObject = self.models.cloudspace.get(int(cloudspaceId))

        # For backwards compatibility, set the secret if it is not filled in
        if len(cloudspaceObject.secret) == 0:
            cloudspaceObject.secret = str(uuid.uuid4())
            self.models.cloudspace.set(cloudspaceObject)

        cloudspace_acl = authenticator.auth({}).getCloudspaceAcl(cloudspaceObject.id)
        cloudspace = {"accountId": cloudspaceObject.accountId,
                      "acl": [{"right": ''.join(sorted(ace['right'])), "type": ace['type'], "userGroupId": ace['userGroupId'],
                               "canBeDeleted": ace['canBeDeleted']} for _, ace in cloudspace_acl.iteritems()],
                      "description": cloudspaceObject.descr,
                      "id": cloudspaceObject.id,
                      "name": cloudspaceObject.name,
                      "publicipaddress": getIP(cloudspaceObject.publicipaddress),
                      "status": cloudspaceObject.status,
                      "location": cloudspaceObject.location,
                      "secret": cloudspaceObject.secret}
        return cloudspace

    @authenticator.auth(acl={'cloudspace': set('U')})
    @audit()
    def deleteUser(self, cloudspaceId, userId, recursivedelete=False, **kwargs):
        """
        Revoke user access from the cloudspace

        :param cloudspaceId: id of the cloudspace
        :param userId: id or emailaddress of the user to remove
        :param recursivedelete: recursively revoke access permissions from owned cloudspaces
                                and machines
        :return True if user access was revoked from cloudspace
        """
        cloudspace = self.models.cloudspace.get(int(cloudspaceId))
        update = False
        for ace in cloudspace.acl:
            if ace.userGroupId == userId:
                cloudspace.acl.remove(ace)
                update = True
        if update:
            self.models.cloudspace.set(cloudspace)
        else:
            raise exceptions.NotFound('User with the username/emailaddress %s does not have access '
                                      'on the cloudspace' % userId)

        if recursivedelete:
            # Delete user accessrights from related machines (part of owned cloudspaces)
            for vmachine in self.models.vmachine.search({'cloudspaceId': cloudspaceId})[1:]:
                vmachineupdate = False
                vmachineobj = self.models.vmachine.get(vmachine['id'])
                for ace in vmachineobj.acl:
                    if ace.userGroupId == userId:
                        vmachineobj.acl.remove(ace)
                        vmachineupdate = True
                if vmachineupdate:
                    self.models.vmachine.set(vmachineobj)

        return update

    @audit()
    def list(self, **kwargs):
        """
        List all cloudspaces the user has access to

        :return list with every element containing details of a cloudspace as a dict
        """
        ctx = kwargs['ctx']
        user = ctx.env['beaker.session']['user']
        query = {'status': 'DISABLED'}
        disabledaccounts = self.models.account.search(query)[1:]
        disabled = [account['id'] for account in disabledaccounts]
        cloudspaceaccess = set()

        # get cloudspaces access via account
        q = {'acl.userGroupId': user, 'status': {'$ne': 'DISABLED'}}
        query = {'$query': q, '$fields': ['id']}
        accountaccess = set(ac['id'] for ac in self.models.account.search(query)[1:])
        q = {'accountId': {'$in': list(accountaccess)}}
        query = {'$query': q, '$fields': ['id']}
        cloudspaceaccess.update(cs['id'] for cs in self.models.cloudspace.search(query)[1:])

        # get cloudspaces access via atleast one vm
        q = {'acl.userGroupId': user, 'status': {'$ne': 'DESTROYED'}}
        query = {'$query': q, '$fields': ['cloudspaceId']}
        cloudspaceaccess.update(vm['cloudspaceId'] for vm in self.models.vmachine.search(query)[1:])

        fields = ['id', 'name', 'descr', 'status', 'accountId','acl','publicipaddress','location']
        q = {"accountId": {"$nin": disabled},
             "$or": [{"acl.userGroupId": user},
                     {"id": {"$in": list(cloudspaceaccess)} }],
             "status": {"$ne": "DESTROYED"}}
        query = {'$query': q, '$fields': fields}
        cloudspaces = self.models.cloudspace.search(query)[1:]

        for cloudspace in cloudspaces:
            account = self.models.account.get(cloudspace['accountId'])
            cloudspace['publicipaddress'] = getIP(cloudspace['publicipaddress'])
            cloudspace['accountName'] = account.name
            cloudspace_acl = authenticator.auth({}).getCloudspaceAcl(cloudspace['id'])
            cloudspace['acl'] = [{"right": ''.join(sorted(ace['right'])), "type": ace['type'],
                                  "userGroupId": ace['userGroupId'], "canBeDeleted": ace['canBeDeleted']} for _, ace in cloudspace_acl.iteritems()]
            for acl in account.acl:
                if acl.userGroupId == user.lower() and acl.type == 'U':
                    cloudspace['accountAcl'] = acl
                    cloudspace['userRightsOnAccountBilling'] = True
            cloudspace['accountDCLocation'] = account.DCLocation

        return cloudspaces

    @authenticator.auth(acl={'cloudspace': set('A')})
    @audit()
    def update(self, cloudspaceId, name, maxMemoryCapacity, maxDiskCapacity, **kwargs):
        """
        Update the cloudspace name and capacity parameters

        :param cloudspaceId: id of the cloudspace
        :param name: name of the cloudspace
        :param maxMemoryCapacity: max size of memory in space(in GB)
        :param maxDiskCapacity: max size of aggregated disks(in GB)
        :return id of updated cloudspace

        """
        # put your code here to implement this method
        raise NotImplementedError("not implemented method update")

    @authenticator.auth(acl={'cloudspace': set('X')})
    def getDefenseShield(self, cloudspaceId, **kwargs):
        """
        Get information about the defense shield

        param:cloudspaceId id of the cloudspace
        :return dict with defense shield details
        """
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if len(fw) == 0:
            raise exceptions.NotFound('Incorrect cloudspace or there is no corresponding gateway')

        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        pwd = str(uuid.uuid4())
        self.netmgr.fw_set_password(fwid, 'admin', pwd)
        location = self.hrd.get('instance.openvcloud.cloudbroker.defense_proxy')


        url = '%s/ovcinit/%s/' % (location,getIP(cloudspace.publicipaddress))
        result = {'user': 'admin', 'password': pwd, 'url': url}
        return result
