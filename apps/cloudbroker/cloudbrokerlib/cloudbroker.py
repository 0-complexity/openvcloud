from .netmgr import NetManager
from .utils import getJobTags, Dummy, removeConfusingChars
import random
import time
import string
import yaml
import re
import netaddr
import uuid
from JumpScale import j
from libcloud.compute.base import NodeAuthPassword
from JumpScale.portal.portal import exceptions
from CloudscalerLibcloud.compute.drivers.libvirt_driver import (
    CSLibvirtNodeDriver,
    StorageException,
    NotEnoughResources,
    Node,
    NetworkInterface,
    PhysicalVolume,
)
from cloudbrokerlib import enums, network, resourcestatus
from cloudbrokerlib.statushandler import StatusHandler
from CloudscalerLibcloud.utils.connection import CloudBrokerConnection
from cloudbrokerlib.statushandler import StatusHandler
from CloudscalerLibcloud.utils.gridconfig import GridConfig

DEFAULTIOPS = 2000


class OSIS(object):
    def __init__(self):
        self._osis = j.clients.osis.getByInstance("main")

    def __getattr__(self, attr):
        namespace = j.clients.osis.getNamespace(attr, self._osis)
        setattr(self, attr, namespace)
        return namespace


ujson = j.db.serializers.ujson
db = OSIS()
models = db.cloudbroker
sysmodels = db.system
_providers = dict()


def CloudProvider(stackId):
    if stackId not in _providers:
        stack = models.stack.get(stackId)
        kwargs = dict()
        kwargs["stack"] = stack
        driver = CSLibvirtNodeDriver(**kwargs)
        client = None
        if "libcloud__libvirt" not in j.apps.system.contentmanager.getActors():
            client = j.clients.portal.getByInstance("cloudbroker")
        cb = CloudBrokerConnection(client)
        driver.set_backend(cb)
        _providers[stackId] = driver
    return _providers[stackId]


class CloudBroker(object):
    _resourceProviderId2StackId = dict()

    def __init__(self):
        self.Dummy = Dummy
        self._actors = None
        self.syscl = sysmodels
        self.cbcl = models
        self.vcl = j.clients.osis.getNamespace("vfw")
        self.agentcontroller = j.clients.agentcontroller.get()
        self.machine = Machine(self)
        self.cloudspace = CloudSpace(self)
        self.netmgr = NetManager(self)

    def executeJumpscript(
        self,
        organization,
        name,
        nid=None,
        role=None,
        args={},
        all=False,
        timeout=600,
        wait=True,
        queue=u"",
        gid=None,
        errorreport=True,
        transporttimeout=None,
        _agentid=0,
    ):
        kwargs = locals().copy()
        kwargs.pop("self")
        kwargs["tags"] = getJobTags()
        return self.agentcontroller.executeJumpscript(**kwargs)

    def scheduleCmd(
        self,
        gid,
        nid,
        cmdcategory,
        cmdname,
        args={},
        jscriptid=None,
        queue=u"",
        log=True,
        timeout=None,
        roles=[],
        wait=False,
        errorreport=False,
        transporttimeout=None,
        _agentid=0,
    ):
        kwargs = locals().copy()
        kwargs.pop("self")
        kwargs["tags"] = getJobTags()
        return self.agentcontroller.scheduleCmd(**kwargs)

    def getImage(self, provider, imageId):
        if imageId not in provider.stack.images:
            provider.stack = models.stack.get(provider.stack.id)
            if imageId not in provider.stack.images:
                return None

        return models.image.get(imageId)

    def getProviderByStackId(self, stackId):
        return CloudProvider(stackId)

    def addDiskToMachine(self, machine, disk):
        return True

    def getProviderByGID(self, gid):
        stacks = models.stack.search({"gid": gid, "status": "ENABLED"})[1:]
        if stacks:
            return self.getProviderByStackId(stacks[0]["id"])
        raise exceptions.ServiceUnavailable(
            "Not enough resources available on current location"
        )

    def markProvider(self, stack, eco):
        stack = models.stack.get(stack.id)
        update = {"error": stack.error + 1}
        if update["error"] >= 2:
            update["status"] = "ERROR"
            update["eco"] = eco.guid
        models.stack.updateSearch({"id": stack.id}, {"$set": update})

    def clearProvider(self, stack):
        models.stack.updateSearch(
            {"id": stack.id}, {"$set": {"error": 0, "eco": None, "status": "ENABLED"}}
        )

    def getIdByReferenceId(self, objname, referenceId):
        obj = self.getObjectByReferenceId(objname, referenceId)
        if obj:
            return obj.id
        else:
            return None

    def getObjectByReferenceId(self, objname, referenceId):
        model = getattr(models, "%s" % objname)
        queryapi = getattr(model, "search")
        query = {"referenceId": referenceId}
        ids = queryapi(query)[1:]
        if ids:
            obj = model.new()
            obj.load(ids[0])
            return obj
        else:
            return None

    def getBestStack(
        self, gid, imageId=None, excludelist=[], memory=None, routeros=False
    ):
        capacityinfo = self.getCapacityInfo(gid, imageId)
        if not capacityinfo:
            raise exceptions.ServiceUnavailable("No available node")

        capacityinfo = [node for node in capacityinfo if node["id"] not in excludelist]
        if not capacityinfo:
            raise exceptions.ServiceUnavailable(
                "No available node with specified resources"
            )

        if routeros:
            capacityinfo.sort(key=lambda k: k["usedros"])

        for provider in capacityinfo:
            if memory is None:
                return provider
            elif memory < provider["freememory"]:
                return provider

        raise exceptions.ServiceUnavailable(
            "No available node with specified resources"
        )

    def getNode(self, machine, driver=None):
        image = models.image.get(machine.imageId)
        cloudspace = models.cloudspace.get(machine.cloudspaceId)
        name = "vm-{}".format(machine.id)
        interfaces = []
        volumes = []
        for nic in machine.nics:
            if nic.type == "bridge":
                bridgename = "space_{:04x}".format(cloudspace.networkId)
                bridgetype = "private"
                networkId = cloudspace.networkId
            elif nic.type == "PUBLIC":
                tags = j.core.tags.getObject(nic.params)
                pool = models.externalnetwork.get(int(tags.tagGet("externalnetworkId")))
                networkId = pool.vlan
                if networkId == 0:
                    bridgename = "public"
                else:
                    bridgename = "ext-{:04x}".format(networkId)
                bridgetype = "PUBLIC"
            else:
                continue
            interfaces.append(
                NetworkInterface(
                    nic.macAddress, nic.deviceName, bridgetype, bridgename, networkId
                )
            )
        for diskId in machine.disks:
            disk = models.disk.get(diskId)
            volume = j.apps.cloudapi.disks.getStorageVolume(disk, driver)
            volumes.append(volume)

        size = {"memory": machine.memory, "vcpus": machine.vcpus}
        extra = {
            "ifaces": interfaces,
            "imagetype": image.type,
            "volumes": volumes,
            "size": size,
            "boottype": image.bootType,
            "bootdev": "hd",
        }
        node = Node(
            id=machine.referenceId,
            name=name,
            state=5,
            public_ips=[],
            private_ips=[],
            driver=driver,
            extra=extra,
        )
        return node

    def getProvider(self, machine):
        if machine.referenceId and machine.stackId:
            return self.getProviderByStackId(machine.stackId)
        return None

    def getProviderAndNode(self, machineId):
        machineId = int(machineId)
        machine = models.vmachine.get(machineId)
        if machine.status in resourcestatus.Machine.INVALID_STATES:
            return None, None, machine
        provider = self.getProvider(machine)
        vmnode = None
        drivertype = "libvirt"
        if provider:
            drivertype = provider.name
            vmnode = provider.ex_get_node_details(machine.referenceId)
        node = self.getNode(machine, provider)
        if vmnode:
            node.state = vmnode.state

        realstatus = (
            enums.MachineStatusMap.getByValue(node.state, drivertype) or machine.status
        )
        if realstatus != machine.status:
            if machine.status not in resourcestatus.Machine.TRANSITION_STATES:
                models.vmachine.updateSearch({"id": machine.id}, {"$set": {"status": realstatus}})
        return provider, node, machine

    def chooseStack(self, machine):
        if models.disk.count({"id": {"$in": machine.disks}, "type": "P"}) == 0:
            cloudspace = models.cloudspace.get(machine.cloudspaceId)
            newstack = self.getBestStack(
                cloudspace.gid, machine.imageId, memory=machine.memory
            )
            if newstack == -1:
                raise exceptions.ServiceUnavailable(
                    "Not enough resources available to start the requested machine"
                )
            machine.stackId = newstack["id"]
            models.vmachine.set(machine)
        return True

    def getActiveSessionsKeys(self):
        return self.agentcontroller.listActiveSessions().keys()

    def getCapacityInfo(self, gid, imageId=None):
        resourcesdata = list()
        activesessions = self.getActiveSessionsKeys()
        if imageId:
            stacks = models.stack.search({"images": imageId, "gid": gid})[1:]
        else:
            stacks = models.stack.search({"gid": gid})[1:]
        nodeids = [int(stack["referenceId"]) for stack in stacks]
        query = {"$query": {"id": {"$in": nodeids}}, "$fields": ["id", "memory"]}
        nodesbyid = {
            node["id"]: node["memory"] for node in self.syscl.node.search(query)[1:]
        }
        grid = self.syscl.grid.get(gid)
        for stack in stacks:
            if stack.get("status", "ENABLED") == "ENABLED":
                nodeid = int(stack["referenceId"])
                if (stack["gid"], nodeid) not in activesessions:
                    continue
                self.getStackCapacity(stack, grid, nodesbyid)
                resourcesdata.append(stack)
        resourcesdata.sort(key=lambda s: s["usedmemory"])
        return resourcesdata

    def getStackCapacity(self, stack, grid, nodesbyid):
        # search for all vms running on the stacks
        usedvms = models.vmachine.search(
            {
                "$fields": ["id", "memory"],
                "$query": {
                    "stackId": stack["id"],
                    "status": {"$nin": resourcestatus.Machine.NON_CONSUMING_STATES},
                },
            }
        )[1:]
        stack["usedvms"] = len(usedvms)
        if usedvms:
            stack["usedmemory"] = sum(vm["memory"] for vm in usedvms)
        else:
            stack["usedmemory"] = 0
        # add vfws
        nodeid = int(stack["referenceId"])
        roscount = self.vcl.virtualfirewall.count({"gid": stack["gid"], "nid": nodeid})
        stack["usedmemory"] += roscount * 128
        stack["usedros"] = roscount
        stack["totalmemory"] = nodesbyid[nodeid]
        reservedmemory = (
            GridConfig(grid, stack["totalmemory"] / 1024.).get("reserved_mem") or 0
        )
        stack["reservedmemory"] = reservedmemory
        stack["freememory"] = (
            stack["totalmemory"] - stack["usedmemory"] - reservedmemory
        )

    def checkUser(self, username, activeonly=True):
        """
        Check if a user exists with the given username or email address

        :param username: username or emailaddress of the user
        :param activeonly: only return activated users if set to True
        :return: User if found
        """
        query = {"$or": [{"id": username}, {"emails": username}]}
        if activeonly:
            query["active"] = True
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
        if len(emailaddress.split(",")) > 1:
            raise exceptions.BadRequest(
                "Cannot update resource invitations for a list of multiple "
                "email addresses"
            )

        for account in self.cbcl.account.search({"acl.userGroupId": emailaddress})[1:]:
            accountobj = self.cbcl.account.get(account["guid"])
            for ace in accountobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = "CONFIRMED"
                    self.cbcl.account.set(accountobj)
                    break

        for cloudspace in self.cbcl.cloudspace.search(
            {"acl.userGroupId": emailaddress}
        )[1:]:
            cloudspaceobj = self.cbcl.cloudspace.get(cloudspace["guid"])
            for ace in cloudspaceobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = "CONFIRMED"
                    self.cbcl.cloudspace.set(cloudspaceobj)
                    break

        for vmachine in self.cbcl.vmachine.search({"acl.userGroupId": emailaddress})[
            1:
        ]:
            vmachineobj = self.cbcl.vmachine.get(vmachine["guid"])
            for ace in cloudspaceobj.acl:
                if ace.userGroupId == emailaddress:
                    # Update userGroupId and status after user registration
                    ace.userGroupId = username
                    ace.status = "CONFIRMED"
                    self.cbcl.vmachine.set(vmachineobj)
                    break

        return True

    def isaccountuserdeletable(self, userace, acl):
        if set(userace.right) != set("ARCXDU"):
            return True
        else:
            otheradmins = filter(
                lambda a: set(a.right) == set("ARCXDU") and a != userace, acl
            )
            if not otheradmins:
                return False
            else:
                return True

    def isValidEmailAddress(self, emailaddress):
        r = re.compile("^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}$")
        return r.match(emailaddress) is not None

    def isValidRole(self, accessrights):
        """
        Validate that the accessrights map to a valid access role on a resource
        'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin

        :param accessrights: string with the accessrights to verify
        :return: role name if a valid set of permissions, otherwise fail with an exception
        """
        if accessrights == "R":
            return "Read"
        elif set(accessrights) == set("RCX"):
            return "Read/Write"
        elif set(accessrights) == set("ARCXDU"):
            return "Admin"
        else:
            raise exceptions.BadRequest(
                'Invalid set of access rights "%s". Please only use "R" '
                'for Read, "RCX" for Read/Write and "ARCXDU" for Admin '
                "access." % accessrights
            )

    def fillResourceLimits(self, resource_limits, preserve_none=False):
        for limit_type in ["CU_M", "CU_D", "CU_C", "CU_NP", "CU_I"]:
            if limit_type not in resource_limits or resource_limits[limit_type] is None:
                resource_limits[limit_type] = None if preserve_none else -1
            elif resource_limits[limit_type] < -1 or resource_limits[limit_type] == 0:
                raise exceptions.BadRequest(
                    "A resource limit should be a positive number or -1 (unlimited)."
                )
            if limit_type == "CU_M":
                resource_limits[limit_type] = resource_limits[limit_type] and float(
                    resource_limits[limit_type]
                )
            else:
                resource_limits[limit_type] = resource_limits[limit_type] and int(
                    resource_limits[limit_type]
                )
        maxVDiskCapacity = resource_limits["CU_D"]
        if (
            maxVDiskCapacity is not None
            and maxVDiskCapacity != -1
            and maxVDiskCapacity < 10
        ):
            raise exceptions.BadRequest("Minimum disk capacity for cloudspace is 10GB.")


class CloudSpace(object):
    def __init__(self, cb):
        self.cb = cb
        self.network = network.Network(db)

    class RequireState(object):
        def __init__(self, states, msg, refresh=True):
            self.states = states if isinstance(states, list) else [states]
            self.msg = msg
            self.refresh = refresh

        def __call__(self, func):
            def wrapper(s, **kwargs):
                spaceId = int(kwargs["cloudspaceId"])
                space = s.models.cloudspace.searchOne({"id": spaceId})
                if not space:
                    raise exceptions.NotFound(
                        "Machine with id %s was not found" % spaceId
                    )
                # if self.refresh:
                #     space = s.get(spaceId)

                if not space["status"] in self.states:
                    raise exceptions.Conflict(self.msg)
                return func(s, **kwargs)

            return wrapper

    def delete(self, cloudspaceId, permanently=False, **kwargs):
        cloudspaceId = int(cloudspaceId)
        # A cloudspace may not contain any resources any more
        query = {
            "cloudspaceId": cloudspaceId,
            "status": {
                "$nin": [
                    resourcestatus.Machine.DESTROYED,
                    resourcestatus.Machine.DELETED,
                ]
            },
        }

        results = models.vmachine.search(query)[1:]
        if len(results) > 0:
            raise exceptions.Conflict(
                "In order to delete a CloudSpace it can not contain Machines."
            )
        # The last cloudspace in a space may not be deleted
        with models.cloudspace.lock(cloudspaceId):
            cloudspace = models.cloudspace.get(cloudspaceId)
            if cloudspace.status == resourcestatus.Cloudspace.DESTROYED:
                return True
            if cloudspace.status == resourcestatus.Cloudspace.DEPLOYING:
                raise exceptions.BadRequest(
                    "Can not delete a CloudSpace that is being deployed."
                )
        
        if permanently:
            target_status = resourcestatus.Cloudspace.DESTROYED
            transition_status = resourcestatus.Cloudspace.DESTROYING
        else:
            target_status = resourcestatus.Cloudspace.DELETED
            transition_status = resourcestatus.Cloudspace.DELETING

        provider = self.cb.getProviderByGID(cloudspace.gid)
        cloudspace.status = (
            resourcestatus.Cloudspace.DESTROYING
            if permanently
            else resourcestatus.Cloudspace.DELETING
        )
        models.cloudspace.set(cloudspace)

        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        if permanently:
            machines = models.vmachine.search(
                {"cloudspaceId": cloudspaceId, "status": resourcestatus.Machine.DELETED}
            )[1:]
            for machine in sorted(
                machines, key=lambda m: m["cloneReference"], reverse=True
            ):
                self.cb.machine.destroy_machine(machine["id"], provider)
              
            cloudspace = self.cb.cloudspace.release_resources(cloudspace)
        else:
            self.cb.netmgr.fw_stop(fwid)
        
        StatusHandler(
            models.cloudspace, cloudspaceId, transition_status
        ).update_status(target_status)

        return True


    def release_resources(self, cloudspace, releasenetwork=True):
        #  delete routeros
        fwguid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        try:
            fw = self.cb.netmgr._getVFWObject(fwguid)
        except exceptions.ServiceUnavailable:
            pass
        else:
            stack = next(
                iter(
                    models.stack.search({"referenceId": str(fw.nid), "gid": fw.gid})[1:]
                ),
                None,
            )
            if stack and stack["status"] != "DECOMISSIONED":
                # destroy vm and model
                self.cb.netmgr.fw_delete(fwguid)
            else:
                # destroy model only
                self.cb.netmgr.fw_destroy(fwguid)
        if cloudspace.networkId and releasenetwork:
            j.apps.libcloud.libvirt.releaseNetworkId(
                cloudspace.gid, cloudspace.networkId
            )
            cloudspace.networkId = None
        if cloudspace.externalnetworkip:
            self.network.releaseExternalIpAddress(
                cloudspace.externalnetworkId, cloudspace.externalnetworkip
            )
            cloudspace.externalnetworkip = None
        return cloudspace

    def get_leases_cloudinit(self, cloudspaceId):
        leases = []
        cloudinit = []
        vms = models.vmachine.search(
            {
                "cloudspaceId": cloudspaceId,
                "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
            },
            size=0,
        )[1:]
        imageIds = list(set(vm["imageId"] for vm in vms))
        images = {
            image["id"]: image
            for image in models.image.search({"id": {"$in": imageIds}})[1:]
        }

        for vm in vms:
            for nic in vm["nics"]:
                if (
                    nic["ipAddress"] != "Undefined"
                    and nic["type"] != "PUBLIC"
                    and nic["macAddress"]
                ):
                    leases.append(
                        {"mac-address": nic["macAddress"], "address": nic["ipAddress"]}
                    )
                    image = images[vm["imageId"]]
                    for account in vm["accounts"]:
                        password = account["password"]
                        break
                    else:
                        continue
                    userdata, metadata = self.cb.machine.get_user_meta_data(
                        vm["name"], password, image["type"], vm.get("userdata")
                    )
                    vmdata = {
                        "mac": nic["macAddress"],
                        "user-data": userdata,
                        "meta-data": metadata,
                    }
                    cloudinit.append(vmdata)
        return leases, cloudinit

    def update_firewall(self, cloudspace, **kwargs):
        fwid = "{}_{}".format(cloudspace.gid, cloudspace.networkId)
        self.cb.netmgr.fw_reapply(fwid)


class Machine(object):
    def __init__(self, cb):
        self.cb = cb
        self.acl = self.cb.agentcontroller

    def cleanup(self, machine, gid=None, volumes=None):
        for diskid in machine.disks:
            if models.disk.exists(diskid):
                models.disk.delete(diskid)
        if models.vmachine.exists(machine.id):
            models.vmachine.delete(machine.id)
        if volumes and gid:
            provider = self.cb.getProviderByGID(gid)
            vdiskguids = []
            for volume in volumes:
                if not isinstance(volume, PhysicalVolume):
                    vdiskguids.append(volume.vdiskguid)
            provider.destroy_volumes_by_guid(vdiskguids)

    def validateCreate(
        self, cloudspace, name, sizeId, imageId, disksize, datadisks, userdata
    ):
        self.assertName(cloudspace.id, name)
        if not disksize:
            raise exceptions.BadRequest("Invalid disksize %s" % disksize)

        if cloudspace.allowedVMSizes:
            if sizeId and sizeId not in cloudspace.allowedVMSizes:
                raise exceptions.BadRequest(
                    "Specified size not allowed for this cloudspace"
                )

        for datadisksize in datadisks:
            if datadisksize > 2000:
                raise exceptions.BadRequest(
                    "Invalid data disk size {}GB max size is 2000GB".format(
                        datadisksize
                    )
                )

        if cloudspace.status == resourcestatus.Cloudspace.DESTROYED:
            raise exceptions.BadRequest(
                "Can not create machine on destroyed Cloud Space"
            )
        elif cloudspace.status == resourcestatus.Cloudspace.DELETED:
            raise exceptions.BadRequest(
                "Can not create machine on deleted Cloud Space, restore it first"
            )

        image = models.image.get(imageId)
        if image.accountId and image.accountId != cloudspace.accountId:
            raise exceptions.BadRequest("Specified image can't be used by this account")
        if disksize < image.size:
            raise exceptions.BadRequest(
                "Disk size of {}GB is to small for image {}, which requires at least {}GB.".format(
                    disksize, image.name, image.size
                )
            )
        if image.status != "CREATED":
            raise exceptions.BadRequest("Image {} is disabled.".format(imageId))
        if userdata:
            if isinstance(userdata, basestring):
                try:
                    data = yaml.load(userdata)
                    if not isinstance(data, dict):
                        raise exceptions.BadRequest("Userdata should be a dictonary")

                except:
                    raise exceptions.BadRequest("Userdata is not a valid yaml string")
            elif not isinstance(userdata, dict):
                raise exceptions.BadRequest("Userdata should be a dictonary")

        maxvms = netaddr.IPNetwork(cloudspace.privatenetwork).size - 5
        if (
            models.vmachine.count(
                {
                    "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
                    "cloudspaceId": cloudspace.id,
                }
            )
            >= maxvms
        ):
            raise exceptions.BadRequest(
                "Can not create more than {} Virtual Machines in this Cloud Space".format(
                    maxvms
                )
            )
        return image

    def assertName(self, cloudspaceId, name):
        if not name or not name.strip():
            raise ValueError("Machine name can not be empty")
        results = models.vmachine.search(
            {
                "cloudspaceId": cloudspaceId,
                "name": name,
                "status": {"$ne": resourcestatus.Machine.DESTROYED},
            }
        )[1:]
        if results:
            raise exceptions.Conflict("Selected name already exists")

    def destroy_machine(self, machineId, provider=None):
        """
        Will force destroy a deleted machine
        :param machineId: int machine id
        :param provider: provider object, if not specified will get grid provider
        """
        machine = models.vmachine.searchOne({"id": machineId})
        if machine["status"] != resourcestatus.Machine.DELETED:
            raise exceptions.BadRequest("Can't destroy a non deleted machine")
        if machine["status"] == resourcestatus.Machine.DESTROYED:
            return
        self.destroy_volumes(machine["disks"], provider)
        models.vmachine.updateSearch(
            {"id": machine["id"]},
            {
                "$set": {
                    "status": resourcestatus.Machine.DESTROYED,
                    "updateTime": int(time.time()),
                }
            },
        )

    def destroy_volumes(self, disks, provider=None):
        """
        Destroys volumes of specified disks
        :param disks: list if disks id
        :param provider: provider object, if not specified will get grid provider
        """
        vdisks = models.disk.search(
            {"$fields": ["referenceId", "gid"], "id": {"$in": disks}}
        )[1:]
        vdiskguids = []
        for vdisk in vdisks:
            _, _, vdiskguid = vdisk["referenceId"].partition("@")
            if vdiskguid:
                vdiskguids.append(vdiskguid)
        provider = provider or self.cb.getProviderByGID(vdisk["gid"])
        provider.destroy_volumes_by_guid(vdiskguids)
        models.disk.updateSearch(
            {"id": {"$in": disks}}, {"$set": {"status": resourcestatus.Disk.DESTROYED}}
        )

    def get_user_meta_data(self, name, defaultuserpassword, imagetype, userdata=None):
        customuserdata = userdata or {}
        if isinstance(customuserdata, basestring):
            customuserdata = yaml.load(customuserdata)
        hostname = re.sub("[^\w\d\-_]", "", name)[:63] or "vm"
        if type not in ["WINDOWS", "Windows"]:
            memrule = 'SUBSYSTEM=="memory", ACTION=="add", TEST=="state", ATTR{state}=="offline", ATTR{state}="online"'
            cpurule = 'SUBSYSTEM=="cpu", ACTION=="add", TEST=="online", ATTR{online}=="0", ATTR{online}="1"'
            runcmds = []
            runcmds.append(
                "echo '{}' > /etc/udev/rules.d/66-hotplug.rules".format(memrule)
            )
            runcmds.append(
                "echo '{}' >> /etc/udev/rules.d/66-hotplug.rules".format(cpurule)
            )
            runcmds.append(["udevadm", "control", "-R"])

            userdata = {
                "password": defaultuserpassword,
                "users": [
                    {
                        "name": "user",
                        "plain_text_passwd": defaultuserpassword,
                        "lock-passwd": False,
                        "shell": "/bin/bash",
                        "sudo": "ALL=(ALL) ALL",
                    }
                ],
                "ssh_pwauth": True,
                "runcmd": runcmds,
                "manage_etc_hosts": True,
                "chpasswd": {"expire": False},
            }
            metadata = {"local-hostname": hostname}
            if "users" in customuserdata:
                users = customuserdata.pop("users", [])
                userdata["users"].extend(users)
            userdata.update(customuserdata)
        else:
            userdata = {}
            metadata = {"admin_pass": defaultuserpassword, "hostname": hostname}
        return userdata, metadata

    def deploy_disks(self, cloudspace, machine, disksize, datadisks, image, ctx):
        datadisks = datadisks or []
        vmid = "vm-{}".format(machine.id)
        disk, volume = j.apps.cloudapi.disks.create_disk(
            cloudspace.accountId,
            cloudspace.gid,
            vmid,
            "Boot Disk",
            size=disksize,
            type="B",
            iops=DEFAULTIOPS,
            imageId=image.id,
            order=0,
        )
        def update_models(diskId):
            models.vmachine.updateSearch(
                {"id": machine.id}, {"$addToSet": {"disks": diskId}}
            )
            models.disk.updateSearch(
                {"id": diskId}, {"$set": {"status": resourcestatus.Disk.ASSIGNED}}
            )
        update_models(disk.id)

        diskoffset = 1
        if cloudspace.type == "routeros":
            password = None
            for account in machine.accounts:
                password = account.password
                break
            if password:
                diskoffset = 2
                userdata, metadata = self.get_user_meta_data(
                    machine.name, password, image.type, machine.userdata
                )
                cloudinitdata = {
                    "userdata": userdata,
                    "metadata": metadata,
                    "edgeclient": volume.edgeclient,
                    "name": vmid,
                }
                disk, _ = j.apps.cloudapi.disks.create_disk(
                    cloudspace.accountId,
                    cloudspace.gid,
                    "Metadata ISO",
                    "Metadata ISO",
                    size=0.1,
                    type="M",
                    iops=DEFAULTIOPS,
                    order=1,
                    cloudinitdata=cloudinitdata,
                )
                update_models(disk.id)               

            # create metadata
        for order, datadisk in enumerate(datadisks):
            order += diskoffset
            disk, _ = j.apps.cloudapi.disks.create_disk(
                cloudspace.accountId,
                cloudspace.gid,
                "Data Disk {}".format(order),
                "Data Disk {}".format(order),
                size=datadisk,
                type="D",
                iops=DEFAULTIOPS,
                order=order,
            )
            update_models(disk.id)               



    def createModel(
        self, name, description, cloudspace, imageId, sizeId, vcpus, memory, userdata
    ):
        image = models.image.get(imageId)
        machine = models.vmachine.new()
        if sizeId:
            machine.sizeId = sizeId
            size = models.size.get(sizeId)
            vcpus = size.vcpus
            memory = size.memory
        machine.memory = memory
        machine.vcpus = vcpus
        machine.cloudspaceId = cloudspace.id
        machine.descr = description
        machine.name = name
        machine.imageId = imageId
        machine.creationTime = int(time.time())
        machine.updateTime = int(time.time())
        machine.type = "VIRTUAL"
        machine.status = resourcestatus.Machine.VIRTUAL
        machine.userdata = userdata
        machine.referenceId = str(uuid.uuid4())

        account = machine.new_account()
        if hasattr(image, "username") and image.username:
            account.login = image.username
        elif image.type != "Custom Templates":
            account.login = "user"
        else:
            account.login = "Custom login"
            account.password = "Custom password"

        if hasattr(image, "password") and image.password:
            account.password = image.password

        if not account.password:
            length = 6
            chars = removeConfusingChars(string.letters + string.digits)
            letters = [
                removeConfusingChars(string.ascii_lowercase),
                removeConfusingChars(string.ascii_uppercase),
            ]
            passwd = "".join(random.choice(chars) for _ in range(length))
            passwd = (
                passwd
                + random.choice(string.digits)
                + random.choice(letters[0])
                + random.choice(letters[1])
            )
            account.password = passwd
        with models.cloudspace.lock("{}_ip".format(cloudspace.id)):
            machine.id = models.vmachine.set(machine)[0]
            nic = machine.new_nic()
            nic.type = "bridge"
            nic.deviceName = "vm-{}-{:04x}".format(machine.id, cloudspace.networkId)
            nic.ipAddress = self.cb.cloudspace.network.getFreeIPAddress(cloudspace)
            nic.macAddress = self.cb.cloudspace.network.getFreeMacAddress(
                cloudspace.gid
            )
            models.vmachine.set(machine)
            
        return machine

    def update_volumes(self, machine, volumes):
        # filter out iso volumes
        disks = filter(lambda v: v.type == "disk", volumes)
        bootdisk = None
        for order, diskid in enumerate(machine.disks):
            disk = models.disk.get(diskid)
            disk.stackId = machine.stackId
            disk.referenceId = disks[order].id
            models.disk.set(disk)
            if disk.type == "B":
                bootdisk = disk

        cdroms = filter(lambda v: v.type == "cdrom", volumes)
        for cdrom in cdroms:
            disk = models.disk.new()
            disk.name = "Metadata iso"
            disk.type = "M"
            disk.stackId = machine.stackId
            disk.accountId = bootdisk.accountId
            disk.gid = bootdisk.gid
            disk.referenceId = cdrom.id
            diskid = models.disk.set(disk)[0]
            machine.disks.append(diskid)
