from JumpScale import j
from JumpScale.baselib.http_client.HttpClient import HTTPError
import logging
import unittest
import uuid
import time
import netaddr
import signal
from nose.tools import TimeExpired
from testconfig import config
import random
import imaplib
import socket
import paramiko
import gevent

SESSION_DATA = {"vms": []}

IMAGE_URL = "ftp://pub:pub1234@ftp.gig.tech/Linux/openwrt/openwrt-18.06-rc1.qcow2"

CDROM_URL = "ftp://pub:pub1234@ftp.gig.tech/Linux/tinycorelinux/Core-9x.iso"


def execute_async_ovc(api, function, **kwargs):
    kwargs["_async"] = True

    def _run():
        taskguid = function(**kwargs)
        while True:
            gevent.sleep(0.5)
            result = api.system.task.get(taskguid=taskguid)
            if result != b"":
                success, result = result
                if not success:
                    raise RuntimeError(result)
                return result

    return gevent.spawn(_run)


class API(object):
    API = {}

    def __init__(self):
        self._models = None
        self._portalclient = None
        self._portalclient2 = None
        self._cloudapi = None
        self._cloudbroker = None

    def __getattr__(self, item):
        def set_api(attr):
            API.API[item] = attr
            setattr(self, item, attr)
            return attr

        if item in API.API:
            attr = API.API[item]
            setattr(self, item, attr)
            return attr
        else:
            if item == "models":
                return set_api(j.clients.osis.getNamespace("cloudbroker"))
            elif item == "portalclient":
                return set_api(j.clients.portal.getByInstance("main"))
            elif item == "portalclient2":
                return set_api(j.clients.portal.getByInstance2("main"))
            else:
                actor = getattr(self.portalclient.actors, item)
                return set_api(actor)
        raise AttributeError(item)


class BaseTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.api = API()
        self.environment = config["main"]["environment"]
        self.environment_url = config["main"]["url"]
        self.protocol = config["main"]["protocol"]
        self.owncloud_user = config["main"]["owncloud_user"]
        self.owncloud_password = config["main"]["owncloud_password"]
        self.owncloud_url = config["main"]["owncloud_url"]

        self.test_email = config["main"]["email"]
        self.email_password = config["main"]["email_password"]
        super(BaseTest, self).__init__(*args, **kwargs)

    def setUp(self):

        self.CLEANUP = {"username": [], "accountId": [], "groupname": []}
        self._testID = self._testMethodName
        self._startTime = time.time()
        self._logger = logging.LoggerAdapter(
            logging.getLogger("openvcloud_testsuite"),
            {"testid": self.shortDescription() or self._testID},
        )

        def timeout_handler(signum, frame):
            raise TimeExpired("Timeout expired before end of test %s" % self._testID)

        # adding a signal alarm for timing out the test if it took longer than 15 minutes
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(3000)

    def default_setup(self, create_default_cloudspace=True):
        self.create_default_cloudspace = create_default_cloudspace
        self.location = self.get_location()["locationCode"]
        self.account_owner = self.username
        self.lg("- create account for :%s" % self.account_owner)
        self.account_id = self.cloudbroker_account_create(
            self.account_owner, self.account_owner, self.email
        )
        self.account_owner_api = self.get_authenticated_user_api(self.account_owner)
        if self.create_default_cloudspace:
            self.lg("- create default cloudspace for :%s" % self.account_owner)
            self.cloudspace_id = self.cloudapi_cloudspace_create(
                account_id=self.account_id,
                location=self.location,
                access=self.account_owner,
                api=self.account_owner_api,
                name="default",
            )

    def acl_setup(self, create_default_cloudspace=True):
        self.default_setup(create_default_cloudspace)
        self.user = self.cloudbroker_user_create()
        self.user_api = self.get_authenticated_user_api(self.user)

    def cloudapi_cloudspace_create(
        self,
        account_id,
        location,
        access,
        api=None,
        name="",
        maxMemoryCapacity=-1,
        maxDiskCapacity=-1,
        maxCPUCapacity=-1,
        maxNumPublicIP=-1,
        allowedVMSizes=None,
        wait=True,
    ):
        api = api or self.api
        name = name or str(uuid.uuid4()).replace("-", "")[0:10]
        cloudspaceId = api.cloudapi.cloudspaces.create(
            accountId=account_id,
            location=location,
            access=access,
            name=name,
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNumPublicIP=maxNumPublicIP,
            allowedVMSizes=allowedVMSizes,
        )

        self.assertTrue(cloudspaceId)
        if wait:
            self.wait_for_status(
                "DEPLOYED", api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
            )
        return cloudspaceId

    def cloudbroker_cloudspace_create(
        self,
        account_id,
        location,
        access,
        api=None,
        name="",
        maxMemoryCapacity=-1,
        maxDiskCapacity=-1,
        maxCPUCapacity=-1,
        maxNumPublicIP=-1,
    ):
        if api is None:
            api = self.api
        cloudspaceId = api.cloudbroker.cloudspace.create(
            accountId=account_id,
            location=location,
            access=access,
            name=name or str(uuid.uuid4()).replace("-", "")[0:10],
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNumPublicIP=maxNumPublicIP,
        )
        self.assertTrue(cloudspaceId)
        self.wait_for_status(
            "DEPLOYED", api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
        )
        return cloudspaceId

    def cloudbroker_account_create(
        self,
        name,
        username,
        email,
        maxMemoryCapacity=-1,
        maxVDiskCapacity=-1,
        maxCPUCapacity=-1,
        maxNumPublicIP=-1,
    ):
        accountId = self.api.cloudbroker.account.create(
            name,
            username,
            email,
            maxMemoryCapacity=maxMemoryCapacity,
            maxVDiskCapacity=maxVDiskCapacity,
            maxCPUCapacity=maxCPUCapacity,
            maxNumPublicIP=maxNumPublicIP,
        )
        self.assertTrue(accountId, "Failed to create account for user %s!" % username)
        self.CLEANUP["accountId"].append(accountId)
        self.lg("- account ID: %s" % accountId)
        return accountId

    def cloudbroker_user_create(
        self, username="", email="", password="", group=[], api=None
    ):
        if api is None:
            api = self.api
        username = username or str(uuid.uuid4()).replace("-", "")[0:10]

        api.cloudbroker.user.create(
            username=username,
            emailaddress=email or "%s@example.com" % username,
            password=password or username,
            groups=group,
        )
        self.CLEANUP["username"].append(username)
        return username

    def get_authenticated_user_api(self, username, password=""):
        """
        Create authenticated cloud APIs for a specific user

        :returns user_api: cloud_api authenticated with the user name and password
        """
        url = self.api.cloudapi.locations.getUrl().split("//")[1]
        port = 443 if self.protocol == "https" else 80
        user_api = j.clients.portal.get2(url, port=port)
        user_api.system.usermanager.authenticate(
            name=username, secret=password or username
        )
        return user_api

    def tearDown(self):
        """
        Environment cleanup and logs collection.
        """
        if hasattr(self, "_startTime"):
            executionTime = time.time() - self._startTime
        self.lg("Testcase %s ExecutionTime is %s sec." % (self._testID, executionTime))

    def lg(self, msg):
        self._logger.info(msg)

    def get_cloudspace(self):
        if "cloudspaceid" not in SESSION_DATA:
            cloudspaces = self.api.cloudapi.cloudspaces.list()
            self.assertIsInstance(cloudspaces, list)
            self.assertTrue(cloudspaces)
            SESSION_DATA["cloudspaceid"] = cloudspaces[0]["id"]
        return SESSION_DATA["cloudspaceid"]

    def get_location(self):
        env_location = config["main"]["environment"]
        self.assertTrue(env_location)
        locations = self.api.cloudapi.locations.list()
        self.assertTrue(locations)
        for location in locations:
            if env_location == location["locationCode"]:
                return location
        else:
            raise Exception(
                "can't find the %s environment location in grid" % env_location
            )

    def stop_vm(self, vmid):
        self.api.cloudapi.machines.stop(vmid)
        try:
            self.waitForStatus(vmid, "HALTED", timeout=10)
        except AssertionError:
            self.api.cloudapi.machines.stop(vmid)
            self.waitForStatus(vmid, "HALTED")

    def cloudbroker_create_image(
        self,
        name="",
        url="",
        api="",
        gid=None,
        imagetype="linux",
        boottype="bios",
        username=None,
        password=None,
        account_id=None,
        wait=True,
    ):
        name = name or str(uuid.uuid4()).replace("-", "")[0:10]
        api = api or self.api
        gid = gid or j.application.whoAmI.gid
        url = url or IMAGE_URL
        api.cloudbroker.image.createImage(
            name=name,
            url=url,
            gid=gid,
            imagetype=imagetype,
            boottype=boottype,
            username=username,
            password=password,
            accountId=account_id,
        )
        ccl = j.clients.osis.getNamespace("cloudbroker")
        query = {"name": name}
        if wait:
            self.wait_for_status("CREATED", ccl.image.searchOne, query=query)
        else:
            self.wait_for_set(ccl.image.searchOne, query=query)
        image_id = ccl.image.searchOne({"$fields": ["id"], "$query": query})["id"]
        return image_id

    def get_image(self):
        images = self.api.cloudapi.images.list()
        for image in images:
            if "Ubuntu" in image["name"]:
                return image
        else:
            raise Exception("There is no Ubuntu images available. ")

    def get_size(self, cloudspace_id):
        sizes = self.api.cloudapi.sizes.list(cloudspaceId=cloudspace_id)
        self.assertTrue(sizes)
        return sizes[0]

    def get_size_by_id(self, sizeId):
        sizes = self.api.cloudapi.sizes.list(location=self.location)
        size = [size for size in sizes if size["id"] == sizeId]

        if not size:
            return None

        return size[0]

    def cloudapi_create_machine(
        self,
        cloudspace_id,
        api="",
        name="",
        size_id=0,
        vcpus=None,
        memory=None,
        image_id=None,
        disksize=10,
        datadisks=[],
        wait=True,
        stackId=None,
        async=False,
    ):
        api = api or self.api
        name = name or str(uuid.uuid4())
        image_id = image_id or self._get_image_id(api)

        if vcpus and memory:
            sizeId = None
        else:
            sizeId = size_id or self.get_size(cloudspace_id)["id"]

        if not stackId:
            if async:
                return execute_async_ovc(
                    api.portalclient2,
                    api.portalclient2.cloudbroker.machine.create,
                    cloudspaceId=cloudspace_id,
                    name=name,
                    sizeId=sizeId,
                    vcpus=vcpus,
                    memory=memory,
                    imageId=image_id,
                    disksize=disksize,
                    datadisks=datadisks,
                )
            else:
                machine_id = api.cloudapi.machines.create(
                    cloudspaceId=cloudspace_id,
                    name=name,
                    sizeId=sizeId,
                    vcpus=vcpus,
                    memory=memory,
                    imageId=image_id,
                    disksize=disksize,
                    datadisks=datadisks,
                )
        else:
            if async:
                return execute_async_ovc(
                    api.portalclient2,
                    api.portalclient2.cloudbroker.machine.createOnStack,
                    cloudspaceId=cloudspace_id,
                    name=name,
                    sizeId=sizeId,
                    vcpus=vcpus,
                    memory=memory,
                    imageId=image_id,
                    disksize=disksize,
                    stackid=stackId,
                )
            else:
                machine_id = api.cloudbroker.machine.createOnStack(
                    cloudspaceId=cloudspace_id,
                    name=name,
                    sizeId=sizeId,
                    vcpus=vcpus,
                    memory=memory,
                    imageId=image_id,
                    disksize=disksize,
                    stackid=stackId,
                )

        self.assertTrue(machine_id)
        if wait:
            self.wait_for_status(
                "DEPLOYED", api.cloudapi.cloudspaces.get, cloudspaceId=cloudspace_id
            )
        machine = api.cloudapi.machines.get(machineId=machine_id)
        self.assertEqual(machine["status"], "RUNNING")
        return machine_id

    def _get_image_id(self, api):
        images = api.cloudapi.images.list()
        image_ids = [i["id"] for i in images if "Ubuntu" in i["name"]]
        self.assertTrue(image_ids)
        return image_ids[0]

    def cloudbroker_create_machine(
        self,
        cloudspace_id,
        api="",
        name="",
        size_id=0,
        image_id=None,
        disksize=10,
        datadisks=[],
        wait=True,
        stackId=None,
    ):
        api = api or self.api
        name = name or str(uuid.uuid4())
        sizeId = size_id or self.get_size(cloudspace_id)["id"]
        if image_id == None:
            images = api.cloudapi.images.list()
            image_id = [i["id"] for i in images if "Ubuntu" in i["name"]]
            self.assertTrue(image_id)
            image_id = image_id[0]

        if not stackId:
            machine_id = api.cloudbroker.machine.create(
                cloudspaceId=cloudspace_id,
                name=name,
                sizeId=sizeId,
                imageId=image_id,
                disksize=disksize,
                datadisks=datadisks,
            )
        else:
            machine_id = api.cloudbroker.machine.createOnStack(
                cloudspaceId=cloudspace_id,
                name=name,
                sizeId=sizeId,
                imageId=image_id,
                disksize=disksize,
                stackid=stackId,
            )
        self.assertTrue(machine_id)
        if wait:
            self.wait_for_status(
                "DEPLOYED", api.cloudapi.cloudspaces.get, cloudspaceId=cloudspace_id
            )
        machine = api.cloudapi.machines.get(machineId=machine_id)
        self.assertEqual(machine["status"], "RUNNING")
        return machine_id

    def cloudbroker_group_create(self, name, group_domain, description):

        group_status = self.api.system.usermanager.createGroup(
            name=name, domain=group_domain, description=description
        )
        self.lg("groupstatues %s " % group_status)
        self.assertTrue(group_status)
        self.CLEANUP["groupname"] = [name]

    def cloudbroker_group_edit(self, groupname, groupdomain, description, users):

        edit_succeed = self.api.system.usermanager.editGroup(
            name=groupname, domain=groupdomain, description="test", users=users
        )
        return edit_succeed

    def get_user_group_list(self, username):
        user_group_list = self.api.system.usermanager.usergroupsget(user=username)
        self.lg("get groups for user %s" % username)

        user_group_list = self.api.system.usermanager.usergroupsget(user=username)
        return user_group_list

    def wait_for_status(self, status, func, timeout=300, **kwargs):
        """
        A generic utility method that gets a resource and wait for resource status

        :param status: the status to wait for
        :param func: the function used to get the resource
        :param kwargs: the parameters to be sent to func to get resource
        """
        resource = func(**kwargs)  # get resource
        self.wait_for_set(func, timeout, **kwargs)
        for _ in xrange(timeout):
            if resource["status"] == status:
                break
            time.sleep(1)
            resource = func(**kwargs)  # get resource
        self.assertEqual(resource["status"], status)

    def wait_for_set(self, func, timeout=300, **kwargs):
        """
        A generic utility method that gets a resource and wait for it be set with a value

        :param func: the function used to get the resource
        :param kwargs: the parameters to be sent to func to get resource
        """
        resource = func(**kwargs)
        for _ in xrange(timeout):
            if resource:
                break
            time.sleep(1)
            resource = func(**kwargs)
        self.assertTrue(resource)

    def wait_for_stack_status(self, stackId, status, timeout=30):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        for _ in range(timeout):
            if ccl.stack.get(stackId).status == status:
                return True
            else:
                time.sleep(3)

        return False

    def wait_for_node_status(self, nodeId, status, timeout=30):
        scl = j.clients.osis.getNamespace("system")
        for _ in range(timeout):
            if scl.node.get(int(nodeId)).status == status:
                return True
            else:
                time.sleep(3)
        return False

    def get_machine_ipaddress(self, machineId):
        machine_info = self.api.cloudapi.machines.get(machineId=machineId)
        ip_address = machine_info["interfaces"][0]["ipAddress"]
        return ip_address

    def add_user_to_account(self, account_id, user, accesstype, api=""):
        api = api or self.api
        api.cloudapi.accounts.addUser(
            accountId=account_id, userId=user, accesstype=accesstype
        )

        account = self.api.cloudapi.accounts.get(accountId=account_id)
        self.assertIn(user, [acl["userGroupId"] for acl in account["acl"]])
        acl_user = [acl for acl in account["acl"] if acl["userGroupId"] == user][0]
        self.assertEqual(acl_user["right"], accesstype)

    def add_user_to_cloudspace(self, cloudspace_id, user, accesstype, api=""):
        api = api or self.api
        api.cloudapi.cloudspaces.addUser(
            cloudspaceId=cloudspace_id, userId=user, accesstype=accesstype
        )

        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        self.assertIn(user, [acl["userGroupId"] for acl in cloudspace["acl"]])
        acl_user = [acl for acl in cloudspace["acl"] if acl["userGroupId"] == user][0]
        self.assertEqual(acl_user["right"], accesstype)

    def add_user_to_machine(self, machine_id, user, accesstype, api=""):
        api = api or self.api
        api.cloudapi.machines.addUser(
            machineId=machine_id, userId=user, accesstype=accesstype
        )

        machine = self.api.cloudapi.machines.get(machineId=machine_id)
        self.assertIn(user, [acl["userGroupId"] for acl in machine["acl"]])
        acl_user = [acl for acl in machine["acl"] if acl["userGroupId"] == user][0]
        self.assertEqual(acl_user["right"], accesstype)

    def _machine_list_scenario_base(self):
        self.lg("1- Create 1 machine for account owner")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )
        self.lg("2- Give the user read access to the newly created machine")
        self.account_owner_api.cloudapi.machines.addUser(
            machineId=machine_id, userId=self.user, accesstype="R"
        )

        self.lg("3- Try list user's machines, should return list with 1 machine")
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 1, "Failed to list all account owner machines!")

    def _machine_addUser_scenario_base(self):
        self.lg("1- Creating machine to the account_owner' default cloud space")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("2- Give the user write access to the cloud space")
        self.account_owner_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.cloudspace_id, userId=self.user, accesstype="CRX"
        )
        self.lg("3- Creating user2")
        self.user2 = self.cloudbroker_user_create()
        self.user2_api = self.get_authenticated_user_api(self.user2)

        self.lg("4- The user gives user2 write access to the newly created machine")
        self.user_api.cloudapi.machines.addUser(
            machineId=machine_id, userId=self.user2, accesstype="CRX"
        )
        machine = self.api.cloudapi.machines.get(machine_id)
        return machine

    def add_portforwarding(
        self,
        machine_id,
        api="",
        cloudspace_id="",
        cs_publicip="",
        cs_publicport=444,
        vm_port=22,
        protocol="tcp",
        wait_vm_ip=True,
    ):
        api = api or self.api
        # wait until machine takes an ip
        if wait_vm_ip:
            time.sleep(60)

        cloudspace_id = cloudspace_id or self.cloudspace_id
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        cs_publicip = cs_publicip or str(
            netaddr.IPNetwork(cloudspace["publicipaddress"]).ip
        )
        api.cloudapi.portforwarding.create(
            cloudspaceId=cloudspace_id,
            publicIp=cs_publicip,
            publicPort=cs_publicport,
            machineId=machine_id,
            localPort=vm_port,
            protocol=protocol,
        )
        return cs_publicip

    def cloudbroker_add_portforwarding(
        self,
        machine_id,
        api="",
        cloudspace_id="",
        cs_publicip="",
        cs_publicport=444,
        vm_port=22,
        protocol="tcp",
    ):
        api = api or self.api
        # wait until machine takes an ip
        time.sleep(60)

        cloudspace_id = cloudspace_id or self.cloudspace_id
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        cs_publicip = cs_publicip or str(
            netaddr.IPNetwork(cloudspace["publicipaddress"]).ip
        )
        api.cloudbrocker.machine.createPortForward(
            destPort=cs_publicport,
            machineId=machine_id,
            localPort=vm_port,
            proto=protocol,
        )

        return cs_publicip

    def get_cloudspace_network_id(self, cloudspaceID):
        # This function take the cloudspace ID and return its network ID
        return self.api.models.cloudspace.get(cloudspaceID).networkId

    def get_node_gid(self, stackId):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        scl = j.clients.osis.getNamespace("system")
        nodeId = ccl.stack.get(stackId).referenceId
        return scl.node.get(int(nodeId)).gid

    def create_disk(self, account_id, gid=None, size=10, disk_type="D", maxiops=2000):
        if not gid:
            stackId = self.get_running_stackId()
            gid = self.get_node_gid(stackId)
        disk_id = self.api.cloudapi.disks.create(
            accountId=account_id,
            gid=gid,
            name=str(uuid.uuid4())[0:8],
            description="test",
            size=size,
            type=disk_type,
            iops=maxiops,
        )
        return disk_id

    def create_cdrom(self, name="", api="", url="", gid=None, account_id=None):
        name = name or str(uuid.uuid4()).replace("-", "")[0:10]
        api = api or self.api
        gid = gid or j.application.whoAmI.gid
        url = url or CDROM_URL
        query = {"name": name}
        ccl = j.clients.osis.getNamespace("cloudbroker")
        self.api.cloudbroker.image.createCDROMImage(
            name=name, url=url, gid=gid, accountId=account_id
        )
        self.wait_for_status("CREATED", ccl.disk.searchOne, query=query)
        disk_id = ccl.disk.searchOne({"$fields": ["id"], "$query": query})["id"]
        return disk_id

    def create_external_network(self, name="", gid=None, vlan=None, account_id=None):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        name = name or str(uuid.uuid4()).replace("-", "")[0:10]
        gid = gid or j.application.whoAmI.gid
        account_id = account_id or self.account_id
        base = ".".join([str(random.randint(0, 254)) for _ in range(3)])
        subnet = base + ".0/24"
        gateway = base + ".1"
        startip = base + ".10"
        endip = base + ".20"
        external_network_id = self.api.cloudbroker.iaas.addExternalNetwork(
            name=name,
            subnet=subnet,
            gateway=gateway,
            startip=startip,
            endip=endip,
            gid=gid,
            vlan=vlan,
            accountId=account_id
        )
        self.wait_for_set(ccl.externalnetwork.get, key=external_network_id)
        return external_network_id

    def get_vm_ssh_publicport(self, vm_id, wait_vm_ip=True):
        vm = self.api.cloudapi.machines.get(machineId=vm_id)
        pfs = self.api.cloudapi.portforwarding.list(
            cloudspaceId=vm["cloudspaceid"], machineId=vm_id
        )
        vm_cs_publicports = [pf["publicPort"] for pf in pfs if pf["localPort"] == "22"]
        if vm_cs_publicports:
            vm_cs_publicport = vm_cs_publicports[0]
        else:
            vm_cs_publicport = random.randint(50000, 65000)
            self.add_portforwarding(
                vm_id,
                cloudspace_id=vm["cloudspaceid"],
                cs_publicip=vm_cs_publicports,
                cs_publicport=vm_cs_publicport,
                wait_vm_ip=wait_vm_ip,
            )
        return vm_cs_publicport

    def send_file_from_vm_to_another(self, vm1_client, vm2_id, file_loc):
        vm2 = self.api.cloudapi.machines.get(machineId=vm2_id)
        vm_2_login = vm2["accounts"][0]["login"]
        vm_2_password = vm2["accounts"][0]["password"]
        vm2_ip = vm2["interfaces"][0]["ipAddress"]
        vm1_client.execute("apt install sshpass -y", sudo=True)
        cmd = "sshpass -p {} scp -o StrictHostKeyChecking=no '{}' {}@{}:".format(
            vm_2_password, file_loc, vm_2_login, vm2_ip
        )
        vm1_client.execute(cmd)

    def get_vm_connection(
        self, vm_id, wait_vm_ip=True, password=None, login=None, pb_port=None
    ):
        vm = self.api.cloudapi.machines.get(machineId=vm_id)
        cloudspace_publicip = self.api.cloudapi.cloudspaces.get(
            cloudspaceId=vm["cloudspaceid"]
        )["publicipaddress"]
        password = password or vm["accounts"][0]["password"]
        login = login or vm["accounts"][0]["login"]
        cloudspace_publicport = pb_port or self.get_vm_ssh_publicport(
            vm_id, wait_vm_ip=wait_vm_ip
        )
        for i in range(5):
            try:
                connection = j.remote.cuisine.connect(
                    cloudspace_publicip, cloudspace_publicport, password, login
                )
                connection.user(login)
                connection.fabric.state.output["running"] = False
                connection.fabric.state.output["stdout"] = False
                connection.run("ls")
                break
            except socket.error as ex:
                print(ex)
                continue
        return connection

    def assign_IP_to_vm_external_netowrk(self, vm_id):
        vm_nics = self.api.cloudapi.machines.get(machineId=vm_id)["interfaces"]
        vm_ext_nic = [x for x in vm_nics if "externalnetworkId" in x["params"]][0]
        self.assertTrue(vm_ext_nic)
        vm_ext_ip = vm_ext_nic["ipAddress"]
        ext_mac_addr = vm_ext_nic["macAddress"]
        vmclient = VMClient(vm_id)
        response = vmclient.execute(
            "ifconfig -a |grep  %s| cut -f1  -d ' '" % ext_mac_addr
        )
        ext_interface_name = response[1].read()
        ext_interface_name = ext_interface_name[: ext_interface_name.find("\r")]
        vmclient.execute(
            "ip a a %s dev %s" % (vm_ext_ip, ext_interface_name), sudo=True
        )
        vmclient.execute(
            "nohup bash -c 'ip l s dev %s up </dev/null >/dev/null 2>&1 & '"
            % ext_interface_name,
            sudo=True,
        )
        time.sleep(5)
        vm_ext_ip = vm_ext_ip[: vm_ext_ip.find("/")]
        return vm_ext_ip, ext_interface_name

    def get_vm_public_ssh_client(self, vm_id, vm_ip=None, password=None, login=None):
        vm = self.api.cloudapi.machines.get(machineId=vm_id)
        if not vm_ip:
            vm_nics = vm["interfaces"]
            vm_ip = [x for x in vm_nics if "externalnetworkId" in x["params"]][0][
                "ipAddress"
            ]
            vm_ip = vm_ip[: vm_ip.find("/")]

        password = password or vm["accounts"][0]["password"]
        login = login or vm["accounts"][0]["login"]
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(vm_ip, username=login, password=password)
        return ssh_client

    def get_running_nodeId(self, except_nodeid=None):
        osiscl = j.clients.osis.getByInstance("main")
        nodecl = j.clients.osis.getCategory(osiscl, "system", "node")
        nodes = nodecl.simpleSearch({})
        nodes = [node for node in nodes if "cpunode" in node["roles"]]
        for node in nodes:
            if int(node["id"]) != except_nodeid and node["status"] == "ENABLED":
                return int(node["id"])
        else:
            return None

    def get_running_stackId(self, except_stackid=""):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        scl = j.clients.osis.getNamespace("system")
        stacks_list = ccl.stack.list()
        if except_stackid:
            stacks_list.remove(except_stackid)
        for stackId in stacks_list:
            nodeId = ccl.stack.get(stackId).referenceId
            node = scl.node.get(int(nodeId))
            if node.status == "ENABLED":
                return stackId
        return False

    def get_physical_node_id(self, cloudspaceID):
        # This function take the cloudspace ID and return its physical node ID
        netID = self.get_cloudspace_network_id(cloudspaceID)
        vcl = j.clients.osis.getNamespace("vfw")
        return vcl.virtualfirewall.get(
            "%s_%s" % (j.application.whoAmI.gid, str(netID))
        ).nid

    def get_machine_nodeID(self, machineId):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        machine = ccl.vmachine.get(machineId)
        stackID = machine.stackId
        nodeID = ccl.stack.get(stackID).referenceId
        return int(nodeID)

    def get_machine_stackId(self, machineId):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        machine = ccl.vmachine.get(machineId)
        stackId = machine.stackId
        return stackId

    def get_email_data(self, Email, password):
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(Email, password)
        mail.select()
        result, data = mail.search(None, "ALL")
        latest_email_id = data[0].split()[-1]
        result, email_data = mail.fetch(latest_email_id, "(UID BODY[TEXT])")
        raw_email = email_data[0][1]
        return raw_email

    def get_nodeId_to_move_VFW_to(self, current_VFW_nodeId=-1):
        ccl = j.clients.osis.getNamespace("cloudbroker")
        scl = j.clients.osis.getNamespace("system")
        stacks = ccl.stack.list()
        for stackId in stacks:
            nodeId = int(ccl.stack.get(stackId).referenceId)
            node = scl.node.get(int(nodeId))
            if (
                node.status == "ENABLED"
                and "fw" in node.roles
                and nodeId != current_VFW_nodeId
            ):
                return nodeId
        else:
            return False

    def execute_command_on_physical_node(self, command, nodeid):
        # This function execute a command on a physical real node
        acl = j.clients.agentcontroller.get()
        output = acl.executeJumpscript(
            "jumpscale", "exec", nid=nodeid, args={"cmd": command}
        )
        if output["state"] == "OK":
            if "ERROR" not in output["result"][1]:
                return output["result"][1]
            else:
                raise NameError("This command: " + command + " is wrong")
        else:
            raise NameError("Node result state is not OK")


class BasicACLTest(BaseTest):
    def setUp(self):
        """
        Setup environment for the test case.
        """
        super(BasicACLTest, self).setUp()

        self.username = str(uuid.uuid4()).replace("-", "")[
            0:10
        ] + self.shortDescription().split(" ")[0].lower().replace("-", "")
        self.lg(" ***************************** ")
        self.lg("setUp -- create user %s" % self.username)
        password = self.username
        self.email = "%s@example.com" % str(uuid.uuid4())
        self.CLEANUP["username"] = [self.username]
        self.api.cloudbroker.user.create(self.username, self.email, password)

    def tearDown(self):
        """
        Environment cleanup and logs collection.
        """
        api = API()
        accountIds = self.CLEANUP.get("accountId")
        if accountIds:
            for account in accountIds:
                self.lg("Teardown -- delete account: %s" % account)
                try:
                    api.cloudbroker.account.delete(
                        accountId=account, reason="Teardown delete", permanently=True
                    )
                except HTTPError as e:
                    self.lg("Error when deleting account {}".format(account))

        users = self.CLEANUP.get("username")
        if users:
            for user in users:
                self.lg("Teardown -- delete user: %s" % user)
                api.cloudbroker.user.delete(user)
        groups = self.CLEANUP.get("groupname")
        if groups:
            # print groups
            for group in groups:
                self.lg("Teardown -- delete group: %s" % group)
                self.api.system.usermanager.deleteGroup(id=group)
        super(BasicACLTest, self).tearDown()


class VMClient:
    def __init__(
        self,
        vmid,
        login=None,
        password=None,
        port=None,
        ip=None,
        external_network=False,
        timeout=30,
    ):
        """
        param: vmid: virtual machine id.
        param: login: virtual machine username.
        param: password: virtual machine password.
        param: port: virtual machine ssh port.
        param: ip: virtual machine ip (default: cloudspace public ip).
        param: external_network: if True param ip will be vm's ip of the external network interface.
        param: timeout: max retries to get vm connection default(30 second).
        """
        self.api = API()
        self.machine = self.api.cloudapi.machines.get(vmid)
        self.cloudspace = self.api.cloudapi.cloudspaces.get(
            self.machine["cloudspaceid"]
        )
        self.login = login or self.machine["accounts"][0]["login"]
        self.password = password or self.machine["accounts"][0]["password"]
        self.cs_public_ip = str(
            netaddr.IPNetwork(self.cloudspace["publicipaddress"]).ip
        )
        self.ip = ip or self.cs_public_ip
        self.port = port or self.get_vm_ssh_port()

        if external_network:
            self.ip = ip or self.get_machine_ip(external_network)
            self.port = 22

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        for _ in range(timeout):
            try:
                self.client.connect(
                    self.ip, port=self.port, username=self.login, password=self.password
                )
                break
            except:
                time.sleep(3)
        else:
            raise

    def get_machine_ip(self, external_network):
        nics = self.machine["interfaces"]
        if external_network:
            external_network_nic = [
                x for x in nics if "externalnetworkId" in x["params"]
            ]
            if not external_network_nic:
                raise AssertionError("Can't find external network interface")

            vmip = external_network_nic[0]["ipAddress"]
            return vmip[: vmip.find("/")]
        else:
            return nics[0]["ipAddress"]

    def get_vm_ssh_port(self):
        machine_id = self.machine["id"]
        cloudspace_id = self.cloudspace["id"]
        port_forwards = self.api.cloudapi.portforwarding.list(cloudspace_id, machine_id)
        vm_cs_publicports = [
            pf["publicPort"] for pf in port_forwards if pf["localPort"] == "22"
        ]
        if vm_cs_publicports:
            vm_cs_publicport = int(vm_cs_publicports[0])
        else:
            vm_cs_publicport = random.randint(50000, 65000)
            self.api.cloudapi.portforwarding.create(
                cloudspaceId=cloudspace_id,
                publicIp=self.cs_public_ip,
                publicPort=vm_cs_publicport,
                machineId=machine_id,
                localPort=22,
                protocol="tcp",
            )

        return vm_cs_publicport

    def execute(self, cmd, timeout=None, sudo=False, wait=True):
        if sudo and self.login != "root":
            cmd = 'echo "{}" | sudo -S {}'.format(self.password, cmd)

        stdin, stdout, stderr = self.client.exec_command(
            cmd, timeout=timeout, get_pty=True
        )

        if wait:
            stdout.channel.recv_exit_status()

        return stdin, stdout, stderr
