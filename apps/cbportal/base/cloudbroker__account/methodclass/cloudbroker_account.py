from JumpScale import j
import time
import re
from JumpScale.portal.portal.auth import auth
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor, wrap_remote
from JumpScale.portal.portal.async import async


def _send_signup_mail(hrd, **kwargs):
    notifysupport = hrd.get("instance.openvcloud.cloudbroker.notifysupport")
    toaddrs = [kwargs['email']]

    fromaddr = hrd.get('instance.openvcloud.supportemail')
    if notifysupport == '1':
        toaddrs.append(fromaddr)

    message = j.core.portal.active.templates.render('cbportal/email/account/created.html', **kwargs)
    subject = j.core.portal.active.templates.render('cbportal/email/account/created.subject.txt', **kwargs)

    j.clients.email.send(toaddrs, fromaddr, subject, message, files=None)


class cloudbroker_account(BaseActor):
    def __init__(self):
        super(cloudbroker_account, self).__init__()
        self.syscl = j.clients.osis.getNamespace('system')
        self.cloudapi = self.cb.actors.cloudapi

    def _checkAccount(self, accountId):
        account = self.models.account.search({'id': accountId, 'status': {'$ne': 'DESTROYED'}})[1:]
        if not account:
            raise exceptions.NotFound('Account name not found')
        if len(account) > 1:
            raise exceptions.BadRequest('Found multiple accounts for the account ID "%s"' % accountId)

        return account[0]

    @auth(['level1', 'level2', 'level3'])
    @async('Disabling Account', 'Finished disabling account', 'Failed to disable account')
    @wrap_remote
    def disable(self, accountId, reason, **kwargs):
        """
        Disable an account
        param:acountname name of the account
        param:reason reason of disabling
        result
        """
        account = self._checkAccount(accountId)
        account['deactivationTime'] = time.time()
        account['status'] = 'DISABLED'
        self.models.account.set(account)
        # stop all account's machines
        cloudspaces = self.models.cloudspace.search({'accountId': account['id']})[1:]
        for cs in cloudspaces:
            vmachines = self.models.vmachine.search({'cloudspaceId': cs['id'],
                                                     'status': {'$in': ['RUNNING', 'PAUSED']}
                                                     })[1:]
            for vmachine in vmachines:
                self.cloudapi.machines.stop(vmachine['id'])
        return True

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def create(self, name, username, emailaddress, location, maxMemoryCapacity=-1,
               maxVDiskCapacity=-1, maxCPUCapacity=-1, maxNASCapacity=-1, maxArchiveCapacity=-1,
               maxNetworkOptTransfer=-1, maxNetworkPeerTransfer=-1, maxNumPublicIP=-1, **kwargs):
        accounts = self.models.account.search({'name': name, 'status': {'$ne': 'DESTROYED'}})[1:]
        if accounts:
            raise exceptions.Conflict('Account name is already in use.')

        created = False
        if j.core.portal.active.auth.userExists(username):
            if emailaddress and not self.syscl.user.search({'id': username,
                                                            'emails': emailaddress})[1:]:
                raise exceptions.Conflict('The specified username and email do not match.')

            user = j.core.portal.active.auth.getUserInfo(username)
            emailaddress = user.emails[0] if user.emails else None
        else:
            if not emailaddress:
                raise exceptions.BadRequest('Email address is required for new users.')

            password = j.base.idgenerator.generateGUID()
            self.cb.actors.cloudbroker.user.create(username, emailaddress, password, 'user')
            created = True

        now = int(time.time())

        location = location.lower()

        locationurl = j.apps.cloudapi.locations.getUrl().strip('/')

        account = self.models.account.new()
        account.name = name
        account.creationTime = now
        account.DCLocation = location
        account.company = ''
        account.companyurl = ''
        account.status = 'CONFIRMED'

        account.resourceLimits = {'CU_M': maxMemoryCapacity, 'CU_D': maxVDiskCapacity,
                                  'CU_C': maxCPUCapacity, 'CU_S': maxNASCapacity,
                                  'CU_A': maxArchiveCapacity, 'CU_NO': maxNetworkOptTransfer,
                                  'CU_NP': maxNetworkPeerTransfer, 'CU_I':  maxNumPublicIP}

        ace = account.new_acl()
        ace.userGroupId = username
        ace.type = 'U'
        ace.right = 'CXDRAU'
        ace.status = 'CONFIRMED'
        accountid = self.models.account.set(account)[0]

        signupcredit = self.hrd.getFloat('instance.openvcloud.cloudbroker.signupcredit')
        creditcomment = 'Getting you started'
        if signupcredit > 0.0:
            credittransaction = self.models.credittransaction.new()
            credittransaction.accountId = accountid
            credittransaction.amount = signupcredit
            credittransaction.credit = signupcredit
            credittransaction.currency = 'USD'
            credittransaction.comment = creditcomment
            credittransaction.status = 'CREDIT'
            credittransaction.time = now

            self.models.credittransaction.set(credittransaction)

        self.cloudapi.cloudspaces.create(accountid, location, 'default', username)

        mail_args = {
            'account': name,
            'username': username,
            'email': emailaddress,
            'portalurl': locationurl
        }

        if created:
            # new user.
            validation_token = self.models.resetpasswordtoken.new()
            validation_token.id = j.base.idgenerator.generateGUID()
            validation_token.creationTime = int(time.time())
            validation_token.username = username

            self.models.resetpasswordtoken.set(validation_token)
            mail_args.update({
                'token': validation_token.id
            })

        # if emailaddress:
        #     _send_signup_mail(hrd=self.hrd, **mail_args)

        return accountid

    @auth(['level1', 'level2', 'level3'])
    def enable(self, accountId, reason, **kwargs):
        """
        Enable an account
        param:acountID ID of the account
        param:reason reason of enabling
        result
        """
        account = self._checkAccount(accountId)
        if account['status'] != 'DISABLED':
            raise exceptions.BadRequest('Account is not disabled')

        account['status'] = 'CONFIRMED'
        self.models.account.set(account)
        return True

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def update(self, accountId, name, maxMemoryCapacity, maxVDiskCapacity, maxCPUCapacity,
               maxNASCapacity, maxArchiveCapacity, maxNetworkOptTransfer,
               maxNetworkPeerTransfer, maxNumPublicIP, **kwargs):
        """
        Update an account name or the maximum cloud units set on it
        Setting a cloud unit maximum to -1 will not put any restrictions on the resource

        :param accountId: id of the account to change
        :param name: name of the account
        :param maxMemoryCapacity: max size of memory in GB
        :param maxVDiskCapacity: max size of aggregated vdisks in GB
        :param maxCPUCapacity: max number of cpu cores
        :param maxNASCapacity: max size of primary(NAS) storage in TB
        :param maxArchiveCapacity: max size of secondary(Archive) storage in TB
        :param maxNetworkOptTransfer: max sent/received network transfer in operator
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :return: True if update was successful
        """
        return self.cloudapi.accounts.update(accountId, name, maxMemoryCapacity,
                                             maxVDiskCapacity, maxCPUCapacity, maxNASCapacity,
                                             maxArchiveCapacity, maxNetworkOptTransfer,
                                             maxNetworkPeerTransfer, maxNumPublicIP)

    @auth(['level1', 'level2', 'level3'])
    def delete(self, accountId, reason, **kwargs):
        """
        Complete delete an acount from the system
        """
        account = self._checkAccount(accountId)
        ctx = kwargs['ctx']
        ctx.events.runAsync(self._delete,
                            (accountId, reason, kwargs),
                            {},
                            'Deleting Account %(name)s' % account,
                            'Finished deleting Account',
                            'Failed to delete Account')

    def _delete(self, accountId, reason, kwargs):
        ctx = kwargs['ctx']
        account = self.models.account.get(accountId)
        title = 'Deleting Account %s' % account.name
        account.status = 'DESTROYING'
        self.models.account.set(account)
        query = {'accountId': accountId, 'status': {'$ne': 'DESTROYED'}}

        # first delete all images and dependant vms
        images = self.models.image.search({'accountId': accountId})[1:]
        for image in images:
            ctx.events.sendMessage(title, 'Deleting Image %(name)s' % image)
            for vm in self.models.vmachine.search({'imageId': image['id'], 'status': {'$ne': 'DESTROYED'}})[1:]:
                ctx.events.sendMessage(title, 'Deleting dependant Virtual Machine %(name)s' % image)
                j.apps.cloudbroker.machine.destroy(vm['id'], reason)
            self.cloudapi.images.delete(image['id'])
        cloudspaces = self.models.cloudspace.search(query)[1:]
        for cloudspace in cloudspaces:
            j.apps.cloudbroker.cloudspace._destroy(cloudspace, reason, kwargs['ctx'])
        account = self.models.account.get(accountId)
        account.status = 'DESTROYED'
        self.models.account.set(account)
        return True

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def addUser(self, accountId, username, accesstype, **kwargs):
        """
        Give a user access rights.
        Access rights can be 'R' or 'W'
        param:accountId id of the account
        param:username id of the user to give access or emailaddress to invite an external user
        param:accesstype 'R' for read only access, 'W' for Write access
        result bool
        """
        self._checkAccount(accountId)
        user = self.cb.checkUser(username, activeonly=False)
        if user:
            self.cloudapi.accounts.addUser(accountId, username, accesstype)
        elif self.cb.isValidEmailAddress(username):
            self.cloudapi.accounts.addExternalUser(accountId, username, accesstype)
        else:
            raise exceptions.NotFound('User with username %s is not found' % username)
        return True

    @auth(['level1', 'level2', 'level3'])
    @wrap_remote
    def deleteUser(self, accountId, username, recursivedelete, **kwargs):
        """
        Delete a user from the account
        """
        account = self._checkAccount(accountId)
        accountId = account['id']
        user = self.cb.checkUser(username)
        if user:
            userId = user['id']
        else:
            #external user, delete ACE that was added using emailaddress
            userId = username
        self.cloudapi.accounts.deleteUser(accountId, userId, recursivedelete)
        return True
