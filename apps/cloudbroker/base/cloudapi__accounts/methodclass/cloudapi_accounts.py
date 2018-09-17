from JumpScale import j
from cloudbrokerlib import authenticator, resourcestatus
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal import exceptions


class cloudapi_accounts(BaseActor):
    """
    API Actor api for managing account

    """

    def __init__(self):
        super(cloudapi_accounts, self).__init__()
        self.systemodel = j.clients.osis.getNamespace("system")

    @authenticator.auth(acl={"account": set("U")})
    def addUser(self, accountId, userId, accesstype, explicit=True, **kwargs):
        """
        Give a registered user access rights

        :param accountId: id of the account
        :param userId: username or emailaddress of the user to grant access
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user was added successfully
        """
        user = self.cb.checkUser(userId, activeonly=False)
        if not user:
            raise exceptions.NotFound("User is not registered on the system")
        else:
            # Replace email address with ID
            userId = user["id"]

        self._addACE(
            accountId, userId, accesstype, userstatus="CONFIRMED", explicit=explicit
        )
        try:
            j.apps.cloudapi.users.sendShareResourceEmail(
                user, "account", accountId, accesstype
            )
            return True
        except:
            self.deleteUser(accountId, userId, recursivedelete=False)
            raise

    def _addACE(
        self, accountId, userId, accesstype, userstatus="CONFIRMED", explicit=True
    ):
        """
        Add a new ACE to the ACL of the account

        :param accountId: id of the account
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :param userstatus: status of the user (CONFIRMED or INVITED)
        :return True if ACE was added successfully
        """
        accountId = int(accountId)
        if not self.models.account.exists(accountId):
            raise exceptions.NotFound("Account does not exist")

        self.cb.isValidRole(accesstype)
        account = self.models.account.get(accountId)
        for ace in account.acl:
            if ace.userGroupId == userId:
                raise exceptions.BadRequest(
                    "User already has access rights to this account"
                )

        acl = account.new_acl()
        acl.userGroupId = userId
        acl.type = "U"
        acl.right = accesstype
        acl.status = userstatus
        acl.explicit = explicit
        self.models.account.updateSearch(
            {"id": accountId}, {"$push": {"acl": acl.obj2dict()}}
        )
        return True

    @authenticator.auth(acl={"account": set("U")})
    def updateUser(self, accountId, userId, accesstype, explicit=True, **kwargs):
        """
        Update user access rights

        :param accountId: id of the account
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user access was updated successfully
        """
        accountId = int(accountId)
        if not self.models.account.exists(accountId):
            raise exceptions.NotFound("Account does not exist")

        self.cb.isValidRole(accesstype)
        account = self.models.account.get(accountId)
        for ace in account.acl:
            if ace.userGroupId == userId:
                if not self.cb.isaccountuserdeletable(ace, account.acl):
                    raise exceptions.BadRequest(
                        "User is last admin on the account, cannot change "
                        "user's access rights"
                    )
                break
        else:
            raise exceptions.NotFound("User does not have any access rights to update")

        self.models.account.updateSearch(
            {"id": accountId, "acl.userGroupId": userId},
            {"$set": {"acl.$.right": accesstype, "acl.$.explicit": explicit}},
        )
        return True

    def create(
        self,
        name,
        access,
        maxMemoryCapacity=None,
        maxVDiskCapacity=None,
        maxCPUCapacity=None,
        maxNetworkPeerTransfer=None,
        maxNumPublicIP=None,
        **kwargs
    ):
        """
        Create a extra an account (Method not implemented)

        :param name: name of account to create
        :param access: list of ids of users which have full access to this account
        :param maxMemoryCapacity: max size of memory in GB
        :param maxVDiskCapacity: max size of aggregated vdisks in GB
        :param maxCPUCapacity: max number of cpu cores
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :return int
        """
        raise NotImplementedError("Not implemented method create")

    @authenticator.auth(acl={"account": set("R")})
    def get(self, accountId, **kwargs):
        """
        Get account details

        :param accountId: id of the account
        :return dict with the account details
        """
        account = self.models.account.get(int(accountId)).dump()

        # Filter the acl (after removing the selected user) to only have admins
        admins = filter(lambda a: set(a["right"]) == set("ARCXDU"), account["acl"])
        # Set canBeDeleted to True except for the last admin on the account (if more than 1 admin
        # on account then all can be deleted)
        for ace in account["acl"]:
            if len(admins) <= 1 and ace in admins:
                ace["canBeDeleted"] = False
            else:
                ace["canBeDeleted"] = True
        return account

    @authenticator.auth(acl={"account": set("R")})
    def listTemplates(self, accountId, **kwargs):
        """
        List templates which can be managed by this account

        :param accountId: id of the account
        :return dict with the template images for the given account
        """
        fields = [
            "id",
            "name",
            "description",
            "type",
            "UNCPath",
            "size",
            "username",
            "accountId",
            "status",
        ]
        q = {"accountId": int(accountId)}
        query = {"$query": q, "$fields": fields}
        results = self.models.image.search(query)[1:]
        return results

    @authenticator.auth(acl={"account": set("U")})
    def deleteUser(self, accountId, userId, recursivedelete=False, **kwargs):
        """
        Revoke user access from the account

        :param acountId: id of the account
        :param userId: id or emailaddress of the user to remove
        :param recursivedelete: recursively revoke access permissions from owned cloudspaces
                                and machines
        :return True if user access was revoked from account
        """
        accountId = int(accountId)
        account = self.models.account.get(accountId)
        for ace in account.acl:
            if ace.userGroupId == userId:
                if not self.cb.isaccountuserdeletable(ace, account.acl):
                    raise exceptions.BadRequest(
                        "User '%s' is the last admin on the account '%s'"
                        % (userId, account.name)
                    )
                break
        else:
            raise exceptions.NotFound(
                'User "%s" does not have access on the account' % userId
            )

        self.models.account.updateSearch(
            {"id": accountId}, {"$pull": {"acl": {"type": "U", "userGroupId": userId}}}
        )

        if recursivedelete:
            # Delete user accessrights from owned cloudspaces
            self.models.cloudspace.updateSearch(
                {"accountId": accountId},
                {"$pull": {"acl": {"type": "U", "userGroupId": userId}}},
            )
            for cloudspace in self.models.cloudspace.search({"accountId": accountId})[
                1:
            ]:
                # Delete user accessrights from related machines (part of owned cloudspaces)
                self.models.vmachine.updateSearch(
                    {"cloudspaceId": cloudspace["id"]},
                    {"$pull": {"acl": {"type": "U", "userGroupId": userId}}},
                )
        return True

    def list(self, **kwargs):
        """
        List all accounts the user has access to

        :return list with every element containing details of a account as a dict
        """
        ctx = kwargs["ctx"]
        user = ctx.env["beaker.session"]["user"]
        fields = ["id", "name", "acl", "creationTime", "updateTime"]
        q = {
            "acl.userGroupId": user,
            "status": {
                "$in": [
                    resourcestatus.Account.DISABLED,
                    resourcestatus.Account.CONFIRMED,
                ]
            },
        }
        query = {"$query": q, "$fields": fields}
        accounts = self.models.account.search(query)[1:]
        return accounts

    @authenticator.auth(acl={"account": set("A")})
    def update(
        self,
        accountId,
        name=None,
        maxMemoryCapacity=None,
        maxVDiskCapacity=None,
        maxCPUCapacity=None,
        maxNetworkPeerTransfer=None,
        maxNumPublicIP=None,
        sendAccessEmails=None,
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
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :return: True if update was successful
        """

        accountobj = (
            self.models.account.get(accountId)
            if self.models.account.exists(accountId)
            else None
        )
        if not accountobj or accountobj.status == resourcestatus.Account.INVALID_STATES:
            raise exceptions.BadRequest("Cannot edit deleted account.")

        if sendAccessEmails == 1:
            sendAccessEmails = True
        elif sendAccessEmails == 0:
            sendAccessEmails = False

        if name:
            accountobj.name = name

        if sendAccessEmails is not None:
            accountobj.sendAccessEmails = sendAccessEmails

        if (
            maxMemoryCapacity
            or maxVDiskCapacity
            or maxCPUCapacity
            or maxNetworkPeerTransfer
            or maxNumPublicIP
        ):
            reservedcloudunits = self.getReservedCloudUnits(accountId)

        if maxMemoryCapacity is not None:
            consumedmemcapacity = self.getConsumedCloudUnitsByType(accountId, "CU_M")
            if maxMemoryCapacity != -1 and maxMemoryCapacity < consumedmemcapacity:
                raise exceptions.BadRequest(
                    "Cannot set the maximum memory capacity to a value "
                    "that is less than the current consumed memory "
                    "capacity %s GB." % consumedmemcapacity
                )
            elif (
                maxMemoryCapacity != -1
                and maxMemoryCapacity < reservedcloudunits["CU_M"]
            ):
                raise exceptions.BadRequest(
                    "Cannot set the maximum memory capacity to a value "
                    "that is less than the current reserved memory "
                    "capacity %s GB by account's cloudspaces."
                    % reservedcloudunits["CU_M"]
                )
            else:
                accountobj.resourceLimits["CU_M"] = maxMemoryCapacity

        if maxVDiskCapacity is not None:
            consumedvdiskcapacity = self.getConsumedCloudUnitsByType(accountId, "CU_D")
            if maxVDiskCapacity != -1 and maxVDiskCapacity < consumedvdiskcapacity:
                raise exceptions.BadRequest(
                    "Cannot set the maximum vdisk capacity to a value that "
                    "is less than the current consumed vdisk capacity %s "
                    "GB." % consumedvdiskcapacity
                )
            elif (
                maxVDiskCapacity != -1 and maxVDiskCapacity < reservedcloudunits["CU_D"]
            ):
                raise exceptions.BadRequest(
                    "Cannot set the maximum vdisk capacity to a value "
                    "that is less than the current reserved vdisk "
                    "capacity %s GB by account's cloudspaces."
                    % reservedcloudunits["CU_D"]
                )
            else:
                accountobj.resourceLimits["CU_D"] = maxVDiskCapacity

        if maxCPUCapacity is not None:
            consumedcpucapacity = self.getConsumedCloudUnitsByType(accountId, "CU_C")
            if maxCPUCapacity != -1 and maxCPUCapacity < consumedcpucapacity:
                raise exceptions.BadRequest(
                    "Cannot set the maximum cpu cores to a value that "
                    "is less than the current consumed cores %s "
                    "GB." % consumedcpucapacity
                )
            elif maxCPUCapacity != -1 and maxCPUCapacity < reservedcloudunits["CU_C"]:
                raise exceptions.BadRequest(
                    "Cannot set the maximum cpu cores to a value "
                    "that is less than the current reserved cpu cores "
                    "%s by account's cloudspaces." % reservedcloudunits["CU_C"]
                )
            else:
                accountobj.resourceLimits["CU_C"] = maxCPUCapacity

        if maxNetworkPeerTransfer is not None:
            transferednewtpeer = self.getConsumedCloudUnitsByType(accountId, "CU_NP")
            if (
                maxNetworkPeerTransfer != -1
                and maxNetworkPeerTransfer < transferednewtpeer
            ):
                raise exceptions.BadRequest(
                    "Cannot set the maximum network transfer peering "
                    "to a value that is less than the current  "
                    "sent/received %s GB." % transferednewtpeer
                )
            elif (
                maxNetworkPeerTransfer != -1
                and maxNetworkPeerTransfer < reservedcloudunits["CU_NP"]
            ):
                raise exceptions.BadRequest(
                    "Cannot set the maximum  network transfer peering "
                    "to a value that is less than the current reserved "
                    "transfer %s GB by account's cloudspaces."
                    % reservedcloudunits["CU_NP"]
                )
            else:
                accountobj.resourceLimits["CU_NP"] = maxNetworkPeerTransfer

        if maxNumPublicIP is not None:
            assingedpublicip = self.getConsumedCloudUnitsByType(accountId, "CU_I")
            if maxNumPublicIP != -1 and maxNumPublicIP < assingedpublicip:
                raise exceptions.BadRequest(
                    "Cannot set the maximum number of public IPs "
                    "to a value that is less than the current "
                    "assigned %s." % assingedpublicip
                )
            elif maxNumPublicIP != -1 and maxNumPublicIP < reservedcloudunits["CU_I"]:
                raise exceptions.BadRequest(
                    "Cannot set the maximum number of public IPs to a "
                    "value that is less than the current reserved "
                    "%s by account's cloudspaces." % reservedcloudunits["CU_I"]
                )
            else:
                accountobj.resourceLimits["CU_I"] = maxNumPublicIP

        self.models.account.set(accountobj)
        return True

    # Unexposed actor
    def getConsumedVDiskCapacity(self, accountId):
        """
        Calculate the total consumed disk storage in the account in GB

        :param accountId: id of the accountId that should be checked
        :return: the total consumed disk storage
        """
        disks = self.models.disk.search(
            {
                "$query": {
                    "accountId": accountId,
                    "status": {"$nin": resourcestatus.Disk.INVALID_STATES},
                },
                "$fields": ["sizeMax"],
            },
            size=0,
        )[1:]
        consumeddiskcapacity = sum([d["sizeMax"] for d in disks])
        return consumeddiskcapacity

    @authenticator.auth(acl={"account": set("R")})
    def getConsumedCloudUnits(self, accountId, **kwargs):
        """
        Calculate the currently consumed cloud units for all cloudspaces in the account.

        Calculated cloud units are returned in a dict which includes:
        - CU_M: consumed memory in GB
        - CU_C: number of virtual cpu cores
        - CU_D: consumed virtual disk storage in GB
        - CU_S: consumed primary storage (NAS) in TB
        - CU_A: consumed secondary storage (Archive) in TB
        - CU_NO: sent/received network transfer in operator in GB
        - CU_NP: sent/received network transfer peering in GB
        - CU_I: number of public IPs

        :param accountId: id of the account consumption should be calculated for
        :return: dict with the consumed cloud units
        """
        consumedcudict = {"CU_M": 0, "CU_C": 0, "CU_D": 0, "CU_I": 0}
        # The following keys are unimplemented cloud unit consumptions, will set to 0 until
        # consumption is properly calculated
        unimplementedcu = {"CU_S": 0, "CU_A": 0, "CU_NO": 0, "CU_NP": 0}

        cloudspaces = self.models.cloudspace.search(
            {"@fields": ["id"], "$query": {"accountId": accountId}}
        )[1:]
        deployedcloudspaces = self.models.cloudspace.search(
            {
                "@fields": ["id"],
                "$query": {
                    "accountId": accountId,
                    "status": resourcestatus.Cloudspace.DEPLOYED,
                },
            }
        )[1:]
        cloudspacesIds = [x["id"] for x in cloudspaces]
        deployedcloudspacesIds = [x["id"] for x in deployedcloudspaces]
        consumedcudict = j.apps.cloudapi.cloudspaces.getConsumedCloudUnitsInCloudspaces(
            cloudspacesIds, deployedcloudspacesIds
        )

        consumedcudict.update(unimplementedcu)
        # Calculate disks on account level so as not to miss unattached disks
        consumedcudict["CU_D"] = self.getConsumedVDiskCapacity(accountId)
        return consumedcudict

    @authenticator.auth(acl={"account": set("R")})
    def getConsumedCloudUnitsByType(self, accountId, cutype, **kwargs):
        """
        Calculate the currently consumed cloud units of the specified type for all cloudspaces
        in the account.

        Possible types of cloud units are include:
        - CU_M: returns consumed memory in GB
        - CU_C: returns number of virtual cpu cores
        - CU_D: returns consumed virtual disk storage in GB
        - CU_A: returns consumed secondary storage (Archive) in TB
        - CU_NP: returns sent/received network transfer peering in GB
        - CU_I: returns number of public IPs

        :param accountId: id of the account consumption should be calculated for
        :param cutype: cloud unit resource type
        :return: float/int for the consumed cloud unit of the specified type
        """
        consumedamount = 0
        # get all cloudspaces in this account
        cloudspaces = self.models.cloudspace.search(
            {"@fields": ["id"], "$query": {"accountId": accountId}}
        )[1:]
        cloudspacesIds = [x["id"] for x in cloudspaces]

        # For the following cloud unit types 'CU_S', 'CU_A', 'CU_NO', 'CU_NP', 0 will be returned
        # until proper consumption calculation is implemented
        if cutype == "CU_M":
            consumedamount = j.apps.cloudapi.cloudspaces.getConsumedMemoryInCloudspaces(
                cloudspacesIds
            )
        elif cutype == "CU_C":
            consumedamount = j.apps.cloudapi.cloudspaces.getConsumedCPUCoresInCloudspaces(
                cloudspacesIds
            )
        elif cutype == "CU_D":
            consumedamount = self.getConsumedVDiskCapacity(accountId)
        elif cutype == "CU_NP":
            return 0
        elif cutype == "CU_I":
            # for calculating consumed ips we should consider only deployed cloudspaces
            deployedcloudspaces = self.models.cloudspace.search(
                {
                    "$fields": ["id"],
                    "$query": {
                        "accountId": accountId,
                        "status": resourcestatus.Cloudspace.DEPLOYED,
                    },
                }
            )[1:]
            deployedcloudspacesIds = [x["id"] for x in deployedcloudspaces]
            consumedamount = j.apps.cloudapi.cloudspaces.getConsumedPublicIPsInCloudspaces(
                deployedcloudspacesIds
            )
        else:
            raise exceptions.BadRequest("Invalid cloud unit type: %s" % cutype)

        return consumedamount

    # Unexposed actor
    def getReservedCloudUnits(self, accountId, excludecloudspaceid=None, **kwargs):
        """
        Calculate the currently reserved cloud units by all cloudspaces under an account

        Reserved cloud units will be calculated by summing up all cloud unit limits set on the
        cloudspaces in the account (cloudspaces with unlimited CUs, set to -1, will not be counted
        as they do not reserve any resources)

        Reserved cloud units are returned in a dict which includes:
        - CU_M: consumed memory in GB
        - CU_C: number of virtual cpu cores
        - CU_D: consumed virtual disk storage in GB
        - CU_NP: sent/received network transfer peering in GB
        - CU_I: number of public IPs

        :param accountId: id of the account reserved CUs should be calculated for
        :param excludecloudspaceid: exclude the cloudspace with the specified id when performing the
            calculations
        :return: dict with the reserved cloud units
        """
        reservedcudict = {"CU_M": 0, "CU_C": 0, "CU_D": 0, "CU_I": 0, "CU_NP": 0}

        # Aggregate the total consumed cloud units for all cloudspaces in the account
        for cloudspace in self.models.cloudspace.search(
            {
                "$fields": ["id", "resourceLimits"],
                "$query": {
                    "accountId": accountId,
                    "status": {"$ne": resourcestatus.Cloudspace.DESTROYED},
                },
            }
        )[1:]:
            if (
                excludecloudspaceid is not None
                and cloudspace["id"] == excludecloudspaceid
            ):
                continue

            for cukey, cuvalue in cloudspace["resourceLimits"].iteritems():
                # Ignore cu limit if -1 as it indicates that no limit is set
                if cukey in reservedcudict and cuvalue != -1:
                    reservedcudict[cukey] += cuvalue

        return reservedcudict

    # Unexposed actor
    def checkAvailablePublicIPs(self, accountId, numips=1):
        """
        Check that the required number of ip addresses are available in the given account

        :param accountId: id of the account to check
        :param numips: the required number of public IP addresses that need to be free
        :return: True if check succeeds, otherwise raise a 400 BadRequest error
        """
        # Validate that there still remains enough public IP addresses to assign in account
        resourcelimits = self.models.account.get(accountId).resourceLimits
        if "CU_I" in resourcelimits:
            reservedcus = resourcelimits["CU_I"]

            if reservedcus != -1:
                consumedcus = self.getConsumedCloudUnitsByType(accountId, "CU_I")
                availablecus = reservedcus - consumedcus
                if availablecus < numips:
                    raise exceptions.BadRequest(
                        "Required actions will consume an extra %s public IP(s),"
                        " owning account only has %s free IP(s)."
                        % (numips, availablecus)
                    )
        return True

    # Unexposed actor
    def checkAvailableMachineResources(
        self, accountId, numcpus=0, memorysize=0, vdisksize=0
    ):
        """
        Check that the required machine resources are available in the given account

        :param accountId: id of the accountId to check
        :param numcpus: the required number of cpu cores that need to be free
        :param memorysize: the required memory size in GB that need to be free
        :param vdisksize: the required vdisk size in GB that need to be free
        :return: True if check succeeds, otherwise raise a 400 BadRequest error
        """
        account = self.models.account.get(accountId)
        resourcelimits = account.resourceLimits

        # Validate that there still remains enough cpu cores to assign in account
        if numcpus > 0 and "CU_C" in resourcelimits:
            reservedcus = account.resourceLimits["CU_C"]

            if reservedcus != -1:
                consumedcus = self.getConsumedCloudUnitsByType(accountId, "CU_C")
                availablecus = reservedcus - consumedcus
                if availablecus < numcpus:
                    raise exceptions.BadRequest(
                        "Required actions will consume an extra %s core(s),"
                        " owning account only has %s free core(s)."
                        % (numcpus, availablecus)
                    )

        # Validate that there still remains enough memory capacity to assign in account
        if memorysize > 0 and "CU_M" in resourcelimits:
            reservedcus = account.resourceLimits["CU_M"]

            if reservedcus != -1:
                consumedcus = self.getConsumedCloudUnitsByType(accountId, "CU_M")
                availablecus = reservedcus - consumedcus
                if availablecus < memorysize:
                    raise exceptions.BadRequest(
                        "Required actions will consume an extra %s GB of "
                        "memory, owning account only has %s GB of free "
                        "memory space." % (memorysize, availablecus)
                    )

        # Validate that there still remains enough vdisk capacity to assign in account
        if vdisksize > 0 and "CU_D" in resourcelimits:
            reservedcus = account.resourceLimits["CU_D"]

            if reservedcus != -1:
                consumedcus = self.getConsumedCloudUnitsByType(accountId, "CU_D")
                availablecus = reservedcus - consumedcus
                if availablecus < vdisksize:
                    raise exceptions.BadRequest(
                        "Required actions will consume an extra %s GB of "
                        "vdisk space, owning account only has %s GB of "
                        "free vdisk space." % (vdisksize, availablecus)
                    )

        return True

    @authenticator.auth(acl={"account": set("R")})
    def getConsumption(self, accountId, start, end, **kwargs):
        import datetime
        import zipfile
        from cStringIO import StringIO
        import os
        import glob

        ctx = kwargs["ctx"]
        start_time = datetime.datetime.utcfromtimestamp(start)
        end_time = datetime.datetime.utcfromtimestamp(end)
        root_path = "/opt/jumpscale7/var/resourcetracking/"
        account_path = os.path.join(root_path, str(accountId))
        pathes = glob.glob(os.path.join(account_path, "*/*/*/*"))
        pathes_in_range = list()
        for path in pathes:
            path_list = path.split("/")
            path_date = datetime.datetime(
                int(path_list[-4]),
                int(path_list[-3]),
                int(path_list[-2]),
                int(path_list[-1]),
            )
            if path_date >= start_time and path_date <= end_time:
                pathes_in_range.append((path_date, path))
        if (
            ctx.env.get("HTTP_ACCEPT") == "application/json"
            or ctx.env["REQUEST_METHOD"] == "POST"
        ):
            import CloudscalerLibcloud
            import capnp
            import time

            capnp.remove_import_hook()
            schemapath = os.path.join(
                os.path.dirname(CloudscalerLibcloud.__file__), "schemas"
            )
            resources_capnp = capnp.load(
                os.path.join(schemapath, "resourcemonitoring.capnp")
            )
            consumption = {}
            for date, path in pathes_in_range:
                timestamp = time.mktime(date.timetuple())
                file_path = os.path.join(path, "account_capnp.bin")
                with open(file_path, "rb") as fd:
                    accountdata = resources_capnp.Account.read(fd).to_dict()
                consumption[int(timestamp)] = accountdata
            return consumption
        else:
            ctx.start_response(
                "200 OK",
                [
                    ("content-type", "application/octet-stream"),
                    ("content-disposition", "inline; filename = account.zip"),
                ],
            )
            fp = StringIO()
            with zipfile.ZipFile(fp, "w", zipfile.ZIP_DEFLATED) as zip:
                for _, path in pathes_in_range:
                    file_path = os.path.join(path, "account_capnp.bin")
                    zip.write(file_path, file_path.replace(root_path, ""))
            return fp.getvalue()
