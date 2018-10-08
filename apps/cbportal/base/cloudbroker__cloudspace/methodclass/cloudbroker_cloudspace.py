from JumpScale import j
from cloudbrokerlib import authenticator, resourcestatus
from cloudbrokerlib.authenticator import auth
from JumpScale.portal.portal.async import async
from cloudbrokerlib.baseactor import BaseActor
from cloudbrokerlib import network, netmgr
import netaddr
from JumpScale.portal.portal import exceptions
import time


class cloudbroker_cloudspace(BaseActor):
    def __init__(self):
        super(cloudbroker_cloudspace, self).__init__()
        self.network = network.Network(self.models)
        self.vfwcl = j.clients.osis.getNamespace("vfw")

    def _getCloudSpace(self, cloudspaceId):
        cloudspaceId = int(cloudspaceId)

        cloudspace = self.models.cloudspace.searchOne({"id": cloudspaceId})
        if not cloudspace:
            raise exceptions.NotFound(
                "Cloudspace with id %s not found" % (cloudspaceId)
            )

        if cloudspace["status"] == resourcestatus.Cloudspace.DESTROYED:
            raise exceptions.BadRequest("Specified cloudspace is destroyed")

        return cloudspace

    @auth(groups=["level1", "level2", "level3"])
    def destroy(self, cloudspaceId, reason, permanently=False, name=None, **kwargs):

        """
        Destroys a cloudspace and its machines, vfws and routeros
        """
        try:
            cloudspace = self._getCloudSpace(cloudspaceId)
        except (exceptions.BadRequest, exceptions.NotFound):
            return

        if name and cloudspace["name"] != name:
            raise exceptions.BadRequest("Incorrect cloudspace name specified")
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._destroy,
            args=(cloudspace, reason, permanently, ctx),
            kwargs={},
            title="Deleting Cloud Space",
            success="Finished deleting Cloud Space",
            error="Failed to delete Cloud Space",
        )

    def _destroy(self, cloudspace, reason, permanently, ctx):
        with self.models.cloudspace.lock(cloudspace["id"]):
            cloudspace = self.models.cloudspace.get(cloudspace["id"]).dump()
            if cloudspace["status"] == resourcestatus.Cloudspace.DEPLOYING:
                raise exceptions.BadRequest(
                    "Can not delete a CloudSpace that is being deployed."
                )
        status = cloudspace["status"]
        cloudspace["status"] = resourcestatus.Cloudspace.DESTROYING
        self.models.cloudspace.set(cloudspace)
        title = "Deleting Cloud Space %(name)s" % cloudspace
        try:
            # delete machines
            machine_query = {
                "cloudspaceId": cloudspace["id"],
                "status": {"$ne": resourcestatus.Machine.DESTROYED},
            }
            machines = self.models.vmachine.search(machine_query)[1:]
            for idx, machine in enumerate(
                sorted(machines, key=lambda m: m["cloneReference"], reverse=True)
            ):
                ctx.events.sendMessage(
                    title, "Deleting Virtual Machine %s/%s" % (idx + 1, len(machines))
                )
                j.apps.cloudbroker.machine.destroy(machine["id"], reason, permanently)
        except:
            cloudspace = self.models.cloudspace.get(cloudspace["id"]).dump()
            cloudspace["status"] = status
            self.models.cloudspace.set(cloudspace)
            raise

        if not permanently:
            ctx.events.sendMessage(title, "Stopping Virtual Firewall")
            fwid = "%s_%s" % (cloudspace["gid"], cloudspace["networkId"])
            self.cb.netmgr.fw_stop(fwid)
            cloudspace["status"] = resourcestatus.Cloudspace.DELETED
            current_time = int(time.time())
            cloudspace["deletionTime"] = current_time
            cloudspace["updateTime"] = current_time
        else:
            # delete routeros
            ctx.events.sendMessage(title, "Deleting Virtual Firewall")
            self._destroyVFW(cloudspace["gid"], cloudspace["id"])
            cloudspace = self.models.cloudspace.get(cloudspace["id"])
            self.cb.cloudspace.release_resources(cloudspace)
            cloudspace.status = resourcestatus.Cloudspace.DESTROYED
            cloudspace.updateTime = int(time.time())
        self.models.cloudspace.set(cloudspace)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def restore(self, cloudspaceId, reason, **kwargs):
        return j.apps.cloudapi.cloudspaces.restore(
            cloudspaceId, reason, ctx=kwargs["ctx"]
        )

    @auth(groups=["level3"])
    def destroyCloudSpaces(self, cloudspaceIds, reason, permanently=False, **kwargs):
        """
        Destroys a cloudspacec and its machines, vfws and routeros
        """
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._destroyCloudSpaces,
            args=(cloudspaceIds, reason, permanently, ctx),
            kwargs={},
            title="Destroying Cloud Spaces",
            success="Finished destroying Cloud Spaces",
            error="Failed to destroy Cloud Space",
        )

    def _destroyCloudSpaces(self, cloudspaceIds, reason, permanently, ctx):
        for cloudspaceId in cloudspaceIds:
            cloudspace = self._getCloudSpace(cloudspaceId)
            self._destroy(cloudspace, reason, permanently, ctx)

    @auth(groups=["level1", "level2", "level3"])
    @async("Moving Virtual Firewall", "Finished moving VFW", "Failed to move VFW")
    def moveVirtualFirewallToFirewallNode(self, cloudspaceId, targetNid, **kwargs):
        """
        move the virtual firewall of a cloudspace to a different firewall node
        param:cloudspaceId id of the cloudspace
        param:targetNode name of the firewallnode the virtual firewall has to be moved to
        """
        cloudspace = self._getCloudSpace(cloudspaceId)
        if cloudspace["status"] != resourcestatus.Cloudspace.DEPLOYED:
            raise exceptions.BadRequest(
                "Could not move fw for cloudspace which is not deployed"
            )

        fwid = "%s_%s" % (cloudspace["gid"], cloudspace["networkId"])
        network = self.vfwcl.virtualfirewall.get(fwid)
        if targetNid and network.nid == targetNid:
            raise exceptions.BadRequest("Can not move VFW to the node it is running on")

        if targetNid is None:
            currentstack = self.cb.getObjectByReferenceId("stack", str(network.nid))
            targetNid = int(
                self.cb.getBestStack(
                    cloudspace["gid"], excludelist=[currentstack.id], memory=128
                )["referenceId"]
            )
        stack = self.cb.getObjectByReferenceId("stack", str(targetNid))
        if not stack:
            raise exceptions.NotFound("Couldn't find node with id {}".format(targetNid))
        if stack.status != "ENABLED":
            raise exceptions.BadRequest("Stack is not enabled")

        if not self.cb.netmgr.fw_move(fwid=fwid, targetNid=int(targetNid)):
            # fw_move returned false this mains clean migration failed we will deploy from scratch on new node instead
            self.resetVFW(cloudspaceId, resettype="restore", targetNid=targetNid)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def migrateCloudspace(self, accountId, cloudspace, vfw, sourceip, gid, **kwargs):
        """
        Migrate vfw from another grid
        param:cloudspaceId id of the cloudspace
        param:vfw object to migrate
        """
        location = self.models.location.searchOne({"gid": gid})
        if location is None:
            raise exceptions.BadRequest(
                "Location with gid {} does not exists".format(gid)
            )
        if self.models.account.count({"id": accountId}) == 0:
            raise exceptions.BadRequest(
                "Account with id {} does not exists".format(accountId)
            )
        space = self.models.cloudspace.searchOne(
            {
                "name": cloudspace["name"],
                "status": {"$ne": resourcestatus.Cloudspace.DESTROYED},
                "accountId": accountId,
                "networkId": cloudspace["networkId"],
                "gid": gid,
            }
        )
        vfwobj = self.vfwcl.virtualfirewall.new()
        vfwobj.load(vfw)
        if not space:
            if (
                self.models.cloudspace.count(
                    {"networkId": cloudspace["networkId"], "gid": gid}
                )
                > 0
            ):
                raise exceptions.BadRequest(
                    "Can not migrate cloudspace {} networkId {} is already in use!".format(
                        cloudspace["name"], cloudspace["networkId"]
                    )
                )
            externalnetworkip = netaddr.IPNetwork(cloudspace["externalnetworkip"]).ip
            for externalnetwork in self.models.externalnetwork.search({"gid": gid})[1:]:
                network = netaddr.IPNetwork(
                    "{network}/{subnetmask}".format(**externalnetwork)
                )
                if externalnetworkip in network:
                    break
            else:
                raise exceptions.BadRequest("No external network to host this space")

            newcloudspace = self.models.cloudspace.new()
            newcloudspace.load(cloudspace)
            newcloudspace.id = None
            newcloudspace.guid = None
            newcloudspace.gid = gid
            newcloudspace.accountId = accountId
            newcloudspace.location = location["locationCode"]
            newcloudspace.privatenetwork = str(netmgr.DEFAULTCIDR)
            vfwobj.external.vlan = externalnetwork["vlan"]
            newcloudspace.externalnetworkId = externalnetwork["id"]

            newcloudspace.status = resourcestatus.Cloudspace.MIGRATING
            newcloudspace.id, _, _ = self.models.cloudspace.set(newcloudspace)
        else:
            newcloudspace = self.models.cloudspace.get(space["id"])
            if newcloudspace.status == resourcestatus.Cloudspace.DEPLOYED:
                return newcloudspace.id

        vfwobj.gid = gid
        vfwobj.guid = "{}_{}".format(gid, vfw["id"])
        vfwobj.nid = int(self.cb.getBestStack(gid)["referenceId"])
        vfwobj.domain = str(newcloudspace.id)
        self.vfwcl.virtualfirewall.set(vfwobj)
        if vfwobj.type == "routeros":
            result = self.cb.netmgr.fw_migrate(vfwobj, sourceip, vfwobj.nid)
        else:
            result = self.cb.netmgr._fw_create(
                vfwobj, targetNid=vfwobj.nid, isnew=False
            )
        if result:
            self.models.cloudspace.updateSearch(
                {"id": newcloudspace.id},
                {"$set": {"status": resourcestatus.Cloudspace.DEPLOYED}},
            )
        return newcloudspace.id

    @auth(groups=["level1", "level2", "level3"])
    def getVFW(self, cloudspaceId, **kwargs):
        """
        Get VFW info
        param:cloudspaceId id of the cloudspace
        """
        cloudspaceId = int(cloudspaceId)
        if not self.models.cloudspace.exists(cloudspaceId):
            raise exceptions.NotFound(
                "Cloudspace with id %s not found" % (cloudspaceId)
            )

        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)

        if not self.vfwcl.virtualfirewall.exists(fwid):
            raise exceptions.BadRequest(
                "Can't get VFW of %s cloudspace" % (cloudspace.status)
            )

        network = self.vfwcl.virtualfirewall.get(fwid)
        network_obj = network.dump()

        if self.sysmodels.node.exists(network.nid):
            network_obj["nodename"] = self.sysmodels.node.get(network.nid).name
        else:
            network_obj["nodename"] = str(network.nid)

        try:
            if self.cb.netmgr.fw_check(network.guid, timeout=5):
                network_obj["status"] = "RUNNING"
            else:
                network_obj["status"] = "HALTED"
        except:
            network_obj["status"] = "UNKNOWN"

        return network_obj

    @auth(groups=["level1", "level2", "level3"])
    @async(
        "Deploying Cloud Space",
        "Finished deploying Cloud Space",
        "Failed to deploy Cloud Space",
    )
    def deployVFW(self, cloudspaceId, type, **kwargs):
        """
        Deploy VFW
        param:cloudspaceId id of the cloudspace
        """
        self._getCloudSpace(cloudspaceId)

        return j.apps.cloudapi.cloudspaces.deploy(cloudspaceId=cloudspaceId, type=type)

    @auth(groups=["level1", "level2", "level3"])
    @async(
        "Redeploying Cloud Space",
        "Finished redeploying Cloud Space",
        "Failed to redeploy Cloud Space",
    )
    def resetVFW(self, cloudspaceId, resettype, targetNid=None, **kwargs):
        """
        Restore the virtual firewall of a cloudspace on an available firewall node
        param:cloudspaceId id of the cloudspace
        """
        cloudspaceId = int(cloudspaceId)
        if not self.models.cloudspace.exists(cloudspaceId):
            raise exceptions.NotFound(
                "Cloudspace with id %s not found" % (cloudspaceId)
            )

        if resettype not in ["factory", "restore"]:
            raise exceptions.BadRequest(
                "Invalid value {} for resettype".format(resettype)
            )

        cloudspace = self.models.cloudspace.get(cloudspaceId)
        if cloudspace.status != resourcestatus.Cloudspace.DEPLOYED:
            raise exceptions.BadRequest(
                "Can not reset VFW which is not deployed please deploy instead."
            )

        self._destroyVFW(cloudspace.gid, cloudspaceId, deletemodel=False)
        fwid = "{}_{}".format(cloudspace.gid, cloudspace.networkId)

        # redeploy vfw
        self.cb.netmgr.fw_start(fwid, resettype, targetNid)

    @auth(groups=["level1", "level2", "level3"])
    def applyConfig(self, cloudspaceId, **kwargs):
        cloudspaceId = int(cloudspaceId)
        if not self.models.cloudspace.exists(cloudspaceId):
            raise exceptions.NotFound(
                "Cloudspace with id %s not found" % (cloudspaceId)
            )
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        if cloudspace.status != resourcestatus.Cloudspace.DEPLOYED:
            raise exceptions.BadRequest(
                "Can not reset VFW which is not deployed please deploy instead."
            )
        # restore portforwards and leases
        self.cb.cloudspace.update_firewall(cloudspace)

    @auth(groups=["level1", "level2", "level3"])
    def startVFW(self, cloudspaceId, force=False, **kwargs):
        """
        Start VFW
        param:cloudspaceId id of the cloudspace
        """
        cloudspaceobj = self._getCloudSpace(cloudspaceId)
        cloudspace = self.models.cloudspace.new()
        cloudspace.load(cloudspaceobj)
        if cloudspace.status == resourcestatus.Cloudspace.DELETED:
            raise exceptions.BadRequest("Selected Cloud Space is deleted")
        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        result = self.cb.netmgr.fw_start(fwid=fwid, force=force)
        self.vfwcl.virtualfirewall.updateSearch(
            {"guid": fwid}, {"$set": {"state": "STARTED"}}
        )
        return result

    @auth(groups=["level1", "level2", "level3"])
    def stopVFW(self, cloudspaceId, **kwargs):
        """
        Stop VFW
        param:cloudspaceId id of the cloudspace
        """
        cloudspaceobj = self._getCloudSpace(cloudspaceId)
        cloudspace = self.models.cloudspace.new()
        cloudspace.load(cloudspaceobj)
        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        result = self.cb.netmgr.fw_stop(fwid=fwid)
        self.vfwcl.virtualfirewall.updateSearch(
            {"guid": fwid}, {"$set": {"state": "STOPPED"}}
        )
        return result

    @auth(groups=["level1", "level2", "level3"])
    def destroyVFW(self, cloudspaceId, **kwargs):
        cloudspaceobj = self._getCloudSpace(cloudspaceId)
        cloudspace = self.models.cloudspace.new()
        cloudspace.load(cloudspaceobj)
        self._destroyVFW(cloudspace.gid, cloudspaceId)
        self.cb.cloudspace.release_resources(cloudspace, False)
        cloudspace.status = resourcestatus.Cloudspace.VIRTUAL
        self.models.cloudspace.set(cloudspace)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def changeRouterType(self, cloudspaceId, routertype, **kwargs):
        cloudspace = self._getCloudSpace(cloudspaceId)
        if routertype not in ["vgw"]:
            raise exceptions.BadRequest("Can only change to vfw type vgw")
        fwid = "{gid}_{networkId}".format(**cloudspace)
        if routertype == cloudspace["type"]:
            return
        startfw = False
        if self.cb.netmgr.fw_check(fwid):
            startfw = True
            self.cb.netmgr.fw_stop(fwid)
        self.models.cloudspace.updateSearch(
            {"id": cloudspace["id"]}, {"$set": {"type": routertype}}
        )
        update = {"type": routertype}
        if routertype == "vgw":
            update["host"] = ""
        self.vfwcl.virtualfirewall.updateSearch({"guid": fwid}, {"$set": update})
        if startfw:
            return self.cb.netmgr.fw_start(fwid)
        return

    def _destroyVFW(self, gid, cloudspaceId, deletemodel=True):
        fws = self.cb.netmgr.fw_list(gid=int(gid), domain=str(cloudspaceId))
        if fws:
            try:
                self.cb.netmgr.fw_delete(
                    fwid=fws[0]["guid"], deletemodel=deletemodel, timeout=20
                )
            except exceptions.ServiceUnavailable:
                return False
            return True
        return False

    @auth(groups=["level1", "level2", "level3"])
    def update(
        self,
        cloudspaceId,
        name,
        maxMemoryCapacity,
        maxVDiskCapacity,
        maxCPUCapacity,
        maxNetworkPeerTransfer,
        maxNumPublicIP,
        allowedVMSizes,
        **kwargs
    ):
        """
        Update a cloudspace name or the maximum cloud units set on it
        Setting a cloud unit maximum to -1 will not put any restrictions on the resource

        :param cloudspaceId: id of the cloudspace to change
        :param name: name of the cloudspace
        :param maxMemoryCapacity: max size of memory in GB
        :param maxVDiskCapacity: max size of aggregated vdisks in GB
        :param maxCPUCapacity: max number of cpu cores
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :return: True if update was successful
        """

        resourcelimits = {
            "CU_M": maxMemoryCapacity,
            "CU_D": maxVDiskCapacity,
            "CU_C": maxCPUCapacity,
            "CU_NP": maxNetworkPeerTransfer,
            "CU_I": maxNumPublicIP,
        }
        self.cb.fillResourceLimits(resourcelimits, preserve_none=True)
        maxMemoryCapacity = resourcelimits["CU_M"]
        maxVDiskCapacity = resourcelimits["CU_D"]
        maxCPUCapacity = resourcelimits["CU_C"]
        maxNetworkPeerTransfer = resourcelimits["CU_NP"]
        maxNumPublicIP = resourcelimits["CU_I"]

        return j.apps.cloudapi.cloudspaces.update(
            cloudspaceId=cloudspaceId,
            name=name,
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxVDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNetworkPeerTransfer=maxNetworkPeerTransfer,
            maxNumPublicIP=maxNumPublicIP,
            allowedVMSizes=allowedVMSizes,
        )

    @auth(groups=["level1", "level2", "level3"])
    def create(
        self,
        accountId,
        location,
        name,
        access,
        maxMemoryCapacity=-1,
        maxVDiskCapacity=-1,
        maxCPUCapacity=-1,
        maxNetworkPeerTransfer=-1,
        maxNumPublicIP=-1,
        externalnetworkId=None,
        allowedVMSizes=[],
        privatenetwork=netmgr.DEFAULTCIDR,
        type="routeros",
        **kwargs
    ):
        """
        Create a cloudspace

        :param accountId: id of account to create space for
        :param name: name of space to create
        :param maxMemoryCapacity: max size of memory in GB
        :param maxVDiskCapacity: max size of aggregated vdisks in GB
        :param maxCPUCapacity: max number of cpu cores
        :param maxNetworkPeerTransfer: max sent/received network transfer peering
        :param maxNumPublicIP: max number of assigned public IPs
        :param allowedVMSizes: alowed sizes for a cloudspace
        :param private network: private network
        :param type: Type of router for cloudspace
        :return: True if update was successful
        """
        if not access:
            access = kwargs["ctx"].env["beaker.session"]["user"]

        user = self.sysmodels.user.search({"id": access})[1:]
        if not user:
            raise exceptions.NotFound('Username "%s" not found' % access)

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

        return j.apps.cloudapi.cloudspaces.create(
            accountId=accountId,
            location=location,
            name=name,
            access=access,
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxVDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNetworkPeerTransfer=maxNetworkPeerTransfer,
            maxNumPublicIP=maxNumPublicIP,
            externalnetworkId=externalnetworkId,
            allowedVMSizes=allowedVMSizes,
            privatenetwork=privatenetwork,
            type=type,
            ctx=kwargs["ctx"],
        )

    def _checkCloudspace(self, cloudspaceId):
        cloudspaces = self.models.cloudspace.search({"id": cloudspaceId})[1:]
        if not cloudspaces:
            raise exceptions.NotFound(
                "Cloud space with id %s does not exists" % cloudspaceId
            )

        return cloudspaces[0]

    @auth(groups=["level1", "level2", "level3"])
    def addUser(self, cloudspaceId, username, accesstype, explicit=True, **kwargs):
        """
        Give a user access rights.
        Access rights can be 'R' or 'W'
        param:accountname id of the account
        param:username id of the user to give access or emailaddress to invite an external user
        param:accesstype 'R' for read only access, 'W' for Write access
        result bool
        """
        cloudspace = self._checkCloudspace(cloudspaceId)
        cloudspaceId = cloudspace["id"]
        if cloudspace["status"] == resourcestatus.Cloudspace.DELETED:
            raise exceptions.BadRequest("Selected cloudspace is deleted")
        user = self.cb.checkUser(username, activeonly=False)

        cloudspaceacl = authenticator.auth().getCloudspaceAcl(cloudspaceId)
        if username in cloudspaceacl:
            updated = j.apps.cloudapi.cloudspaces.updateUser(
                cloudspaceId=cloudspaceId,
                userId=username,
                accesstype=accesstype,
                explicit=explicit,
            )
            if not updated:
                raise exceptions.PreconditionFailed(
                    "User already has same access level to owning " "account"
                )
        elif user:
            j.apps.cloudapi.cloudspaces.addUser(
                cloudspaceId=cloudspaceId, userId=username, accesstype=accesstype
            )
        else:
            raise exceptions.NotFound("User with username %s is not found" % username)

        return True

    @auth(groups=["level1", "level2", "level3"])
    def deleteUser(self, cloudspaceId, username, recursivedelete, **kwargs):
        """
        Delete a user from the account
        """
        cloudspace = self._checkCloudspace(cloudspaceId)
        cloudspaceId = cloudspace["id"]
        user = self.cb.checkUser(username)
        if user:
            userId = user["id"]
        else:
            # external user, delete ACE that was added using emailaddress
            userId = username
        j.apps.cloudapi.cloudspaces.deleteUser(
            cloudspaceId=cloudspaceId, userId=userId, recursivedelete=recursivedelete
        )
        return True

    @auth(groups=["level1", "level2", "level3"])
    def deletePortForward(self, cloudspaceId, publicIp, publicPort, proto, **kwargs):
        return j.apps.cloudapi.portforwarding.deleteByPort(
            cloudspaceId=cloudspaceId,
            publicIp=publicIp,
            publicPort=publicPort,
            proto=proto,
        )
