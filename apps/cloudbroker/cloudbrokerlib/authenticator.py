from JumpScale import j
from JumpScale.portal.portal import exceptions
from .cloudbroker import models, sysmodels
from cloudbrokerlib import resourcestatus


class auth(object):
    def __init__(self, acl=None, level=None, groups=None, skipversioncheck=False):
        self.acl = acl or dict()
        for key in self.acl:
            if key not in ["account", "cloudspace", "machine"]:
                raise ValueError(
                    "Unexpected resource type specified in acl dict, only account, "
                    "cloudspace and machine are allowed."
                )
        self.level = level
        self.models = models
        self.groups = groups
        self.skipversioncheck = skipversioncheck

    def getAccountAcl(self, accountId):
        result = dict()
        account = self.models.account.get(accountId)
        if account.status in ["DESTROYED", "DESTROYING"]:
            return result
        for ace in account.acl:
            if ace.type == "U":
                ace_dict = dict(
                    userGroupId=ace.userGroupId,
                    account_right=set(ace.right),
                    right=set(ace.right),
                    type="U",
                    canBeDeleted=True,
                    status=ace.status,
                    explicit=ace.explicit,
                )
                result[ace.userGroupId] = ace_dict
        return result

    def getCloudspaceAcl(self, cloudspaceId):
        result = dict()
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        if cloudspace.status in ["DESTROYED", "DESTROYING"]:
            return result
        for ace in cloudspace.acl:
            if ace.type == "U":
                ace_dict = dict(
                    userGroupId=ace.userGroupId,
                    cloudspace_right=set(ace.right),
                    right=set(ace.right),
                    type="U",
                    canBeDeleted=True,
                    status=ace.status,
                    explicit=ace.explicit,
                )
                result[ace.userGroupId] = ace_dict

        for user_id, ace in self.getAccountAcl(cloudspace.accountId).iteritems():
            if user_id in result:
                result[user_id]["canBeDeleted"] = False
                result[user_id]["right"].update(ace["right"])
                result[user_id]["account_right"] = ace["account_right"]
            else:
                ace["canBeDeleted"] = False
                result[user_id] = ace
        return result

    def getVMachineAcl(self, machineId):
        result = dict()
        machine = self.models.vmachine.get(machineId)

        for ace in machine.acl:
            if ace.type == "U":
                ace_dict = dict(
                    userGroupId=ace.userGroupId,
                    right=set(ace.right),
                    type="U",
                    canBeDeleted=True,
                    status=ace.status,
                )
                result[ace.userGroupId] = ace_dict

        for user_id, ace in self.getCloudspaceAcl(machine.cloudspaceId).iteritems():
            if user_id in result:
                result[user_id]["canBeDeleted"] = not ace['explicit']
                result[user_id]["right"].update(ace["right"])
            else:
                ace["canBeDeleted"] = False
                result[user_id] = ace
        return result

    def expandAclFromVMachine(self, users, groups, vmachine):
        if not self.level or self.level == "machine":
            fullacl = self.expandAcl(users, groups, vmachine.acl)
        else:
            fullacl = set()
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        fullacl.update(self.expandAclFromCloudspace(users, groups, cloudspace))
        return fullacl

    def expandAclFromCloudspace(self, users, groups, cloudspace):
        if not self.level or self.level == "cloudspace":
            fullacl = self.expandAcl(users, groups, cloudspace.acl)
        else:
            fullacl = set()
        account = self.models.account.get(cloudspace.accountId)
        fullacl.update(self.expandAcl(users, groups, account.acl))
        return fullacl

    def expandAclFromAccount(self, users, groups, account):
        fullacl = self.expandAcl(users, groups, account.acl)
        return fullacl

    def expandAcl(self, user, groups, acl):
        fullacl = set()
        for ace in acl:
            right = set(ace.right)
            if ace.type == "U" and ace.userGroupId == user:
                fullacl.update(right)
            elif ace.type == "G" and ace.userGroupId in groups:
                fullacl.update(right)
        return fullacl

    def __call__(self, func):
        def wrapper(*args, **kwargs):
            if "ctx" not in kwargs:
                # call is not performed over rest let it pass
                return func(*args, **kwargs)
            ctx = kwargs["ctx"]
            if (
                not self.skipversioncheck
                and sysmodels.version.count({"status": "INSTALLING"}) != 0
            ):
                raise exceptions.ServiceUnavailable("Can not call API during upgrade")

            tags = j.core.tags.getObject(ctx.env["tags"])
            user = ctx.env["beaker.session"]["user"]
            account = None
            cloudspace = None
            machine = None
            if "machineId" in kwargs and kwargs["machineId"]:
                machine = self.models.vmachine.get(int(kwargs["machineId"]))
                cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
                account = self.models.account.get(cloudspace.accountId)
            elif "diskId" in kwargs and kwargs["diskId"]:
                disk = self.models.disk.get(int(kwargs["diskId"]))
                machinedict = self.models.vmachine.searchOne(
                    {
                        "disks": disk.id,
                        "status": {"$ne": resourcestatus.Machine.DESTROYED},
                    }
                )
                if machinedict:
                    machine = self.models.vmachine.new()
                    machine.load(machinedict)
                    cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
                accountId = disk.accountId
                if accountId:
                    account = self.models.account.get(accountId)
            elif "cloudspaceId" in kwargs and kwargs["cloudspaceId"]:
                cloudspace = self.models.cloudspace.get(int(kwargs["cloudspaceId"]))
                account = self.models.account.get(cloudspace.accountId)
            elif "accountId" in kwargs and kwargs["accountId"]:
                account = self.models.account.get(int(kwargs["accountId"]))

            for key, value in (
                ("accountId", account),
                ("cloudspaceId", cloudspace),
                ("machineId", machine),
            ):
                if value is not None:
                    tags.tagSet(key, str(value.id))
            if "nid" in kwargs and kwargs["nid"]:
                tags.tagSet("nodeId", str(kwargs["nid"]))

            tagstr = str(tags)
            if "nids" in kwargs and kwargs["nids"]:
                for nid in kwargs["nids"]:
                    tagstr += " nodeId:{}".format(nid)

            ctx.env["tags"] = tagstr
            ctx.env["write_audit"]()
            if self.isAuthorized(user, account, cloudspace, machine):
                return func(*args, **kwargs)
            else:
                raise exceptions.Forbidden(
                    """User: "%s" isn't allowed to execute this action.
                        Not enough permissions"""
                    % user
                )

        return wrapper

    def checkAccountStatus(self, requiredaccessrights, account):
        """
        Check if the required action can be executed on an account. If account is 'DISABLED',
        'DESTROYED', 'ERROR' and action requires a permission other than READ, the call should
        fail with 403 Forbidden

        Check if the required action can be executed on an account. If account is
        'DESTROYED' then a 404 NotFound will be returned, else if an action requires a permission
        other than READ, the call will fail with 403 Forbidden if account is not 'CONFIRMED'

        :param requiredaccessrights: the required access rights to access an account or one of
            its cloudspaces or machines
        :param account: the account object its status should be checked
        :raise Exception with 403 Forbidden if action cannot be performed on account or one of
            its cloduspaces or machines

        :raise Exception with 404 if destroyed or 403 Forbidden if non-read action cannot be
            performed on account or one of its cloudspace  or machines
        """
        if account.status == "DESTROYED":
            raise exceptions.NotFound("Could not find an accessible resource.")
        elif requiredaccessrights != set("R") and account.status != "CONFIRMED":
            raise exceptions.Forbidden(
                "Only READ actions can be executed on account "
                "(or one of its cloudspace or machines) with status %s."
                % account.status
            )

    def checkCloudspaceStatus(self, requiredaccessrights, cloudspace):
        """
        Check if the required action can be executed on a cloudspace. If cloudspace is
        'DESTROYED' then a 404 NotFound will be returned, else if an action requires a permission
        other than READ, the call will fail with 403 Forbidden if cloudspace is not in any of the
        statuses 'VIRTUAL', 'DEPLOYING' or'DEPLOYED'

        :param requiredaccessrights: the required access rights to access an cloudspace or one of
            its machines
        :param cloudspace: the cloudspace object its status should be checked
        :raise Exception with 404 if destroyed or 403 Forbidden if non-read action cannot be
            performed on cloudspace or one of its machines
        """
        if cloudspace.status == resourcestatus.Cloudspace.DESTROYED:
            raise exceptions.NotFound("Could not find an accessible resource.")
        elif (
            cloudspace.status == resourcestatus.Cloudspace.DELETED
            and requiredaccessrights != set("D")
        ):
            raise exceptions.NotFound("Could not find an accessible resource.")
        elif requiredaccessrights != set("R") and cloudspace.status not in [
            resourcestatus.Cloudspace.VIRTUAL,
            resourcestatus.Cloudspace.DEPLOYING,
            resourcestatus.Cloudspace.DEPLOYED,
        ]:
            raise exceptions.Forbidden(
                "Only READ actions can be executed on cloudspace "
                "(or one of its machines) with status %s." % cloudspace.status
            )

    def isAuthorized(self, username, account, cloudspace=None, machine=None):
        """
        Check if a user has the authorization to access a resource

        :param username: username of the user to be checked
        :param machine: machine object if authorization should be done on machine level
        :param cloudspace: cloudspace object if authorization should be done on cloudspace level
        :param account: account object if authorization should be done on account level
        :return: True if username is authorized to access the resource, False otherwise
        """
        userobj = j.core.portal.active.auth.getUserInfo(username)
        if not userobj or not userobj.active:
            raise exceptions.Forbidden(
                "User is not allowed to execute action while status is " "inactive."
            )
        groups = userobj.groups
        # add brokeradmin access
        if "admin" in groups:
            return True

        if self.groups:
            groups = set()
            if userobj:
                groups = set(userobj.groups)
            if not groups.intersection(self.groups):
                raise exceptions.Forbidden(
                    "User %s has no access. If you would like to gain access please contact your adminstrator"
                    % username
                )

        if "account" in self.acl and account:
            grantedaccountacl = self.expandAclFromAccount(username, groups, account)
            if self.acl["account"].issubset(grantedaccountacl):
                self.checkAccountStatus(self.acl["account"], account)
                return True

        if "cloudspace" in self.acl and cloudspace:
            grantedcloudspaceacl = self.expandAclFromCloudspace(
                username, groups, cloudspace
            )
            if self.acl["cloudspace"].issubset(grantedcloudspaceacl):
                self.checkAccountStatus(self.acl["cloudspace"], account)
                self.checkCloudspaceStatus(self.acl["cloudspace"], cloudspace)
                return True

        if "machine" in self.acl and machine:
            grantedmachineacl = self.expandAclFromVMachine(username, groups, machine)
            if self.acl["machine"].issubset(grantedmachineacl):
                self.checkAccountStatus(self.acl["machine"], account)
                self.checkCloudspaceStatus(self.acl["machine"], cloudspace)
                return True

        return False
