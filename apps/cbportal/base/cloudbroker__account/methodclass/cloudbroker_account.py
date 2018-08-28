from JumpScale import j
import time
from cloudbrokerlib.authenticator import auth
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal.async import async
from JumpScale.portal.portal import Validators
from cloudbrokerlib import resourcestatus


def _send_signup_mail(hrd, **kwargs):
    notifysupport = hrd.get("instance.openvcloud.cloudbroker.notifysupport")
    toaddrs = [kwargs["email"]]

    fromaddr = hrd.get("instance.openvcloud.supportemail")
    if notifysupport == "1":
        toaddrs.append(fromaddr)

    message = j.core.portal.active.templates.render(
        "cbportal/email/account/created.html", **kwargs
    )
    subject = j.core.portal.active.templates.render(
        "cbportal/email/account/created.subject.txt", **kwargs
    )

    j.clients.email.send(toaddrs, fromaddr, subject, message, files=None)


class cloudbroker_account(BaseActor):
    def __init__(self):
        super(cloudbroker_account, self).__init__()
        self.syscl = j.clients.osis.getNamespace("system")

    def _checkAccount(self, accountId):
        account = self.models.account.searchOne({"id": accountId})
        if not account:
            raise exceptions.NotFound("Account not found")

        if account["status"] == resourcestatus.Account.DESTROYED:
            raise exceptions.BadRequest("Specified account is destroyed")

        return account

    @auth(groups=["level1", "level2", "level3"])
    @async(
        "Disabling Account", "Finished disabling account", "Failed to disable account"
    )
    def disable(self, accountId, reason, **kwargs):
        """
        Disable an account
        param:acountname name of the account
        param:reason reason of disabling
        result
        """
        account = self._checkAccount(accountId)
        account["deactivationTime"] = time.time()
        account["status"] = resourcestatus.Account.DISABLED
        self.models.account.set(account)
        # stop all account's machines
        cloudspaces = self.models.cloudspace.search({"accountId": account["id"]})[1:]
        for cs in cloudspaces:
            vmachines = self.models.vmachine.search(
                {
                    "cloudspaceId": cs["id"],
                    "status": {"$in": resourcestatus.Machine.UP_STATES},
                }
            )[1:]
            for vmachine in vmachines:
                j.apps.cloudapi.machines.stop(machineId=vmachine["id"])
        return True

    @auth(groups=["level1", "level2", "level3"])
    def create(
        self,
        name,
        username,
        emailaddress,
        maxMemoryCapacity=-1,
        maxVDiskCapacity=-1,
        maxCPUCapacity=-1,
        maxNetworkPeerTransfer=-1,
        maxNumPublicIP=-1,
        sendAccessEmails=True,
        **kwargs
    ):

        with self.models.account.lock(name):
            if sendAccessEmails == 1:
                sendAccessEmails = True
            elif sendAccessEmails == 0:
                sendAccessEmails = False
            accounts = self.models.account.search(
                {"name": name, "status": {"$ne": resourcestatus.Account.DESTROYED}}
            )[1:]
            if accounts:
                raise exceptions.Conflict("Account name is already in use.")

            if j.core.portal.active.auth.userExists(username):
                if (
                    emailaddress
                    and not self.syscl.user.search(
                        {"id": username, "emails": emailaddress}
                    )[1:]
                ):
                    raise exceptions.Conflict(
                        "The specified username and email do not match."
                    )

                user = j.core.portal.active.auth.getUserInfo(username)
                emailaddress = user.emails[0] if user.emails else None
            else:
                if not emailaddress:
                    raise exceptions.BadRequest(
                        "Email address is required for new users."
                    )
                Validators.EMAIL(emailaddress)

                password = j.base.idgenerator.generateGUID()
                j.apps.cloudbroker.user.create(
                    username=username,
                    emailaddress=[emailaddress],
                    password=password,
                    groups=["user"],
                )

            now = int(time.time())
            locationurl = j.apps.cloudapi.locations.getUrl().strip("/")

            account = self.models.account.new()
            account.name = name
            account.creationTime = now
            account.updateTime = now
            account.company = ""
            account.companyurl = ""
            account.status = resourcestatus.Account.CONFIRMED
            account.sendAccessEmails = sendAccessEmails

            resourcelimits = {
                "CU_M": maxMemoryCapacity,
                "CU_D": maxVDiskCapacity,
                "CU_C": maxCPUCapacity,
                "CU_NP": maxNetworkPeerTransfer,
                "CU_I": maxNumPublicIP,
            }
            self.cb.fillResourceLimits(resourcelimits)
            account.resourceLimits = resourcelimits

            ace = account.new_acl()
            ace.userGroupId = username
            ace.type = "U"
            ace.right = "CXDRAU"
            ace.status = "CONFIRMED"
            accountid = self.models.account.set(account)[0]

            mail_args = {
                "account": name,
                "username": username,
                "email": emailaddress,
                "portalurl": locationurl,
            }
            kwargs["ctx"].env["tags"] += " accountId:{}".format(accountid)

            if emailaddress:
                _send_signup_mail(hrd=self.hrd, **mail_args)

            return accountid

    @auth(groups=["level1", "level2", "level3"])
    def enable(self, accountId, reason, **kwargs):
        """
        Enable an account
        param:acountID ID of the account
        param:reason reason of enabling
        result
        """
        account = self._checkAccount(accountId)
        if account["status"] != resourcestatus.Account.DISABLED:
            raise exceptions.BadRequest("Account is not disabled")

        account["status"] = resourcestatus.Account.CONFIRMED
        self.models.account.set(account)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def update(
        self,
        accountId,
        name,
        maxMemoryCapacity,
        maxVDiskCapacity,
        maxCPUCapacity,
        maxNetworkPeerTransfer,
        maxNumPublicIP,
        sendAccessEmails,
        **kwargs
    ):
        """
        Update an account name or the maximum cloud units set on it
        Setting a cloud unit maximum to -1 will not put any restrictions on the resource

        :param accountId: id of the account to change
        :param name: name of the account
        :param maxMemoryCapacity: max size of memory in GB
        :param maxVDiskCapacity: max size of aggregated vdisks in GB
        :param maxCPUCapacity: max number of cpu cores
        :param maxNASCapacity: max size of primary(NAS) storage in TB
        :param maxNetworkOptTransfer: max sent/received network transfer in operator
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :return: True if update was successful
        """

        if sendAccessEmails == 1:
            sendAccessEmails = True
        elif sendAccessEmails == 0:
            sendAccessEmails = False

        resourcelimits = {
            "CU_M": maxMemoryCapacity,
            "CU_D": maxVDiskCapacity,
            "CU_C": maxCPUCapacity,
            "CU_NP": maxNetworkPeerTransfer,
            "CU_I": maxNumPublicIP,
        }
        self.cb.fillResourceLimits(resourcelimits)
        maxMemoryCapacity = resourcelimits["CU_M"]
        maxVDiskCapacity = resourcelimits["CU_D"]
        maxCPUCapacity = resourcelimits["CU_C"]
        maxNetworkPeerTransfer = resourcelimits["CU_NP"]
        maxNumPublicIP = resourcelimits["CU_I"]

        return j.apps.cloudapi.accounts.update(
            accountId=accountId,
            name=name,
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxVDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNetworkPeerTransfer=maxNetworkPeerTransfer,
            maxNumPublicIP=maxNumPublicIP,
            sendAccessEmails=sendAccessEmails,
        )

    @auth(groups=["level1", "level2", "level3"])
    def delete(self, accountId, reason, permanently=False, name=None, **kwargs):
        """
        Complete delete an account from the system
        """
        try:
            account = self._checkAccount(accountId)
        except (exceptions.BadRequest, exceptions.NotFound):
            return

        if name and account["name"] != name:
            raise exceptions.BadRequest("Incorrect account name specified")

        startstate = account["status"]

        def restorestate(eco):
            account = self.models.account.get(accountId)
            account.status = startstate
            self.models.account.set(account)

        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._delete,
            (accountId, reason, permanently, kwargs["ctx"]),
            {},
            "Deleting Account %(name)s" % account,
            "Finished deleting Account",
            "Failed to delete Account",
            errorcb=restorestate,
        )

    def _delete(self, accountId, reason, permanently, ctx):
        account = self.models.account.get(accountId)
        title = "Deleting Account %s" % account.name
        account.status = resourcestatus.Account.DESTROYING
        self.models.account.set(account)
        query = {
            "accountId": accountId,
            "status": {"$ne": resourcestatus.Cloudspace.DESTROYED},
        }

        # first delete all images and dependant vms
        images = self.models.image.search({"accountId": accountId})[1:]
        for image in images:
            ctx.events.sendMessage(title, "Deleting Image %(name)s" % image)
            for vm in self.models.vmachine.search(
                {
                    "imageId": image["id"],
                    "status": {"$ne": resourcestatus.Machine.DESTROYED},
                }
            )[1:]:
                ctx.events.sendMessage(
                    title, "Deleting dependant Virtual Machine %(name)s" % image
                )
                j.apps.cloudbroker.machine.destroy(vm["id"], reason, permanently)
            j.apps.cloudapi.images.delete(
                imageId=image["id"], permanently=permanently, ctx=ctx
            )
        cloudspaces = self.models.cloudspace.search(query)[1:]
        for cloudspace in cloudspaces:
            j.apps.cloudbroker.cloudspace._destroy(cloudspace, reason, permanently, ctx)
        disks = self.models.disk.search(
            {"accountId": accountId, "status": {"$ne": resourcestatus.Disk.DESTROYED}},
            size=0,
        )[1:]
        for disk in disks:
            j.apps.cloudapi.disks.delete(disk["id"], False, permanently)
        account = self.models.account.get(accountId)
        if permanently:
            account.status = resourcestatus.Account.DESTROYED
        else:
            account.status = resourcestatus.Account.DELETED
        account.updateTime = int(time.time())
        self.models.account.set(account)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def restore(self, accountId, reason, **kwargs):
        account = self._checkAccount(accountId)
        if account["status"] != resourcestatus.Account.DELETED:
            raise exceptions.BadRequest("Can only restore a deleted account")
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._restore,
            (account, reason, ctx),
            {},
            "Restoring Account %(name)s" % account,
            "Finished restoring Account",
            "Failed to restore Account",
        )

    def _restore(self, account, reason, ctx):
        images = self.models.image.search({"accountId": account["id"]})[1:]
        query = {
            "accountId": account["id"],
            "status": {"$ne": resourcestatus.Cloudspace.DESTROYED},
        }
        cloudspaces = self.models.cloudspace.search(query)[1:]
        title = "Restoring Account %(name)s" % account
        for idx, image in enumerate(images):
            ctx.events.sendMessage(
                title, "Restoring image %s/%s" % (idx + 1, len(images))
            )
            j.apps.cloudapi.images.restore(image["id"], imgrestore="")
        for idx, cloudspace in enumerate(cloudspaces):
            ctx.events.sendMessage(
                title, "Restoring Cloud Space %s/%s" % (idx + 1, len(cloudspaces))
            )
            j.apps.cloudapi.cloudspaces.restore(
                cloudspace["id"], reason, ctx=ctx, accrestore=""
            )
        disks = self.models.disk.search(
            {
                "accountId": account["id"],
                "status": {"$ne": resourcestatus.Disk.DESTROYED},
            },
            size=0,
        )[1:]
        for idx, disk in enumerate(disks):
            ctx.events.sendMessage(
                title, "Restoring Disk %s/%s" % (idx + 1, len(disks))
            )
            j.apps.cloudapi.disks.restore(disk["id"], reason, ctx=ctx, diskrestore="")

        self.models.account.updateSearch(
            {"id": account["id"]},
            {
                "$set": {
                    "status": resourcestatus.Account.CONFIRMED,
                    "updateTime": int(time.time()),
                }
            },
        )
        return True

    @auth(groups=["level3"])
    def deleteAccounts(self, accountIds, reason, permanently=False, **kwargs):
        """
        Destroys accounts
        """
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._deleteAccounts,
            args=(accountIds, reason, permanently, ctx),
            kwargs={},
            title="Destroying Accounts",
            success="Finished destroying Accounts",
            error="Failed to destroy Accounts",
        )

    def _deleteAccounts(self, accountIds, reason, permanently, ctx):
        for accountId in accountIds:
            self._delete(accountId, reason, permanently, ctx)

    @auth(groups=["level1", "level2", "level3"])
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
            j.apps.cloudapi.accounts.addUser(
                accountId=accountId, userId=username, accesstype=accesstype
            )
        else:
            raise exceptions.NotFound("User with username %s is not found" % username)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def deleteUser(self, accountId, username, recursivedelete, **kwargs):
        """
        Delete a user from the account
        """
        account = self._checkAccount(accountId)
        accountId = account["id"]
        user = self.cb.checkUser(username)
        if user:
            userId = user["id"]
        else:
            # external user, delete ACE that was added using emailaddress
            userId = username
        j.apps.cloudapi.accounts.deleteUser(
            accountId=accountId, userId=userId, recursivedelete=recursivedelete
        )
        return True
