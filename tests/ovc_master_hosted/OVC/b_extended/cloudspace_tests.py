# coding=utf-8
import unittest, socket, random
from ....utils.utils import BasicACLTest, VMClient
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from JumpScale import j


class CloudspaceTests(BasicACLTest):
    def setUp(self):
        super(CloudspaceTests, self).setUp()
        self.default_setup()

    def test001_validate_deleted_cloudspace_with_running_machines(self):
        """ OVC-020
        *Test case for validate deleted cloudspace with running machines get destroyed.*

        **Test Scenario:**

        #. Create 3+ vm's possible with different images on new cloudspace, should succeed
        #. Cloudspace status should be DEPLOYED, should succeed
        #. Try to delete the cloudspace with delete, should fail with 409 conflict
        #. Delete the cloudspace with destroy, should succeed
        #. Try list user's cloud spaces, should return empty list, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(
            "1- Create 3+ vm's possible with different images on new cloudspace, "
            "should succeed"
        )
        cloudspace_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )

        images = self.api.cloudapi.images.list()
        for image in images:
            image_name = image["name"]
            self.lg("- using image [%s]" % image_name)
            size = random.choice(
                self.api.cloudapi.sizes.list(cloudspaceId=cloudspace_id)
            )
            self.lg(
                "- using image [%s] with memory size [%s]"
                % (image_name, size["memory"])
            )
            if "Windows" in image_name:
                while True:
                    disksize = random.choice(size["disks"])
                    if disksize > 25:
                        break
            else:
                disksize = random.choice(size["disks"])
            self.lg(
                "- using image [%s] with memory size [%s] with disk "
                "[%s]" % (image_name, size["memory"], disksize)
            )
            machine_id = self.cloudapi_create_machine(
                cloudspace_id=cloudspace_id,
                size_id=size["id"],
                image_id=image["id"],
                disksize=disksize,
            )

        self.lg("2- Cloudspace status should be DEPLOYED, should succeed")
        self.wait_for_status(
            status="DEPLOYED",
            func=self.api.cloudapi.cloudspaces.get,
            timeout=60,
            cloudspaceId=cloudspace_id,
        )

        self.lg(
            "3- Try to delete the cloudspace with delete, should fail with 409 conflict"
        )
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.delete(cloudspaceId=cloudspace_id)

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("4- Delete the cloudspace with destroy, should succeed")
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=cloudspace_id, reason="test", permanently=True
        )

        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspace_id
        )

        self.lg(
            "5- Try list user's cloud spaces, should return empty list, should succeed"
        )
        self.assertFalse(self.api.cloudapi.machines.list(cloudspaceId=cloudspace_id))

        self.lg("%s ENDED" % self._testID)

    @unittest.skip("https://github.com/0-complexity/openvcloud/issues/1121")
    def test002_add_remove_AllowedSize_to_cloudspace(self):
        """ OVC-027
        *Test case for adding and removing  allowed size to a cloudspace.*

        **Test Scenario:**
        #. Create new cloudspace CS1.
        #. Get list of available sizes in location, should succeed.
        #. Add random size to CS1, should succeed.
        #. Check if the size has been added successfully to CS1.
        #. Remove this size from CS1, should succeed.
        #. check if the size has been removed successfully from CS1.
        #. Remove this size again, should fail.
        """

        self.lg("1- Get list of available sizes in location, should succeed.")
        location_sizes = self.api.cloudapi.sizes.list(location=self.location)
        selected_size = random.choice(location_sizes)

        self.lg("2- Add random size to CS1, should succeed")
        response = self.api.cloudapi.cloudspaces.addAllowedSize(
            cloudspaceId=self.cloudspace_id, sizeId=selected_size["id"]
        )
        self.assertTrue(response)

        self.lg("3- Check if the size has been added successfully to CS1")
        cloudspace_sizes = self.api.cloudapi.sizes.list(
            location=self.location, cloudspaceId=self.cloudspace_id
        )
        self.assertIn(selected_size, cloudspace_sizes)

        self.lg("4- Remove this size from CS1, should succeed")
        response = self.api.cloudapi.cloudspaces.removeAllowedSize(
            cloudspaceId=self.cloudspace_id, sizeId=selected_size["id"]
        )
        self.assertTrue(response)

        self.lg("5- check if the size has been removed successfully from CS1")
        cloudspace_sizes = self.api.cloudapi.sizes.list(
            location=self.location, cloudspaceId=self.cloudspace_id
        )
        self.assertNotIn(selected_size, cloudspace_sizes)

        self.lg("6- Remove this size again, should fail")
        with self.assertRaises(ApiError):
            self.api.cloudapi.cloudspaces.removeAllowedSize(
                cloudspaceId=self.cloudspace_id, sizeId=selected_size["id"]
            )

    def test003_executeRouterOSScript(self):
        """ OVC-040
        *Test case for test execute script in routeros.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Execute script on routeros of CS1 to create portforward (PF1), should succeed.
        #. Connect to VM1 through PF1 , should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create virtual machine (VM1)")
        vm_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg(
            "Execute script on routeros of CS1 to create portforward (PF1), should succeed"
        )
        vm = self.api.cloudapi.machines.get(machineId=vm_id)
        cs_ip = self.api.cloudapi.cloudspaces.get(cloudspaceId=vm["cloudspaceid"])[
            "publicipaddress"
        ]
        vm_ip = self.get_machine_ipaddress(vm_id)
        pb_port = random.randint(50000, 60000)
        script = (
            "/ip firewall nat add chain=dstnat action=dst-nat to-addresses=%s to-ports=22 protocol=tcp dst-address=%s dst-port=%s comment=cloudbroker"
            % (vm_ip, cs_ip, pb_port)
        )
        self.api.cloudapi.cloudspaces.executeRouterOSScript(
            self.cloudspace_id, script=script
        )

        self.lg("Connect to VM1 through PF1 , should succeed")
        vm1_client = VMClient(vm_id, port=pb_port)
        stdin, stdout, stderr = vm1_client.execute("ls /")
        self.assertIn("bin", stdout.read())

        self.lg("%s ENDED" % self._testID)

    def test004_disable_cloudspace(self):
        """ OVC-04x
        *Test case for test disable cloudspace.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Disable cloudspace (CS1), should succeed.
        #. Check that cloudspace (CS1)'s private network is halted.
        #. Check virtual machine (VM1) status, should be halted.
        #. Create user without Admin access.
        #. Authenticate (U1), should succeed.
        #. Add user (U1) to cloudsapce (CS1), should succeed.
        #. Try to start virtual machine (VM1) using user (U1), should fail.
        #. Enable cloudspace (CS1), should succeed.
        #. Check that cloudspace (CS1)'s private network is running.
        #. Try to start virtual machine (VM1) using user (U1), should succeed.
        #. Disable cloudspace (CS1) again, should succeed.
        #. Delete cloudspace (CS1) should succeed.
        """

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        self.lg("Disable cloudspace (CS1), should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.disable(
                cloudspaceId=self.cloudspace_id, reason="test"
            )
        )
        self.wait_for_status(
            "DISABLED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Check that cloudspace (CS1)'s private network is halted")
        self.wait_for_status(
            "HALTED",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Check virtual machine (VM1) status, should be halted")
        machine_info = self.api.cloudapi.machines.get(machineId=machineId)
        self.assertEqual(machine_info["status"], "HALTED")

        self.lg("Create user (U1) without Admin access")
        user = self.cloudbroker_user_create()

        self.lg("Authenticate (U1), should succeed")
        user_api = self.get_authenticated_user_api(user)

        self.lg("Add user (U1) to cloudsapce (CS1), should succeed")
        self.add_user_to_cloudspace(self.cloudspace_id, user, "ACDRUX")

        self.lg("Try to start virtual machine (VM1), should fail")
        with self.assertRaises(ApiError) as e:
            user_api.cloudapi.machines.start(machineId=machineId)

        self.lg("Enable cloudspace (CS1), should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.enable(
                cloudspaceId=self.cloudspace_id, reason="test"
            )
        )
        self.wait_for_status(
            "DEPLOYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Check that cloudspace (CS1)'s private network is running")
        self.wait_for_status(
            "RUNNING",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to start virtual machine (VM1) using user (U1), should succeed")
        self.assertTrue(self.api.cloudapi.machines.start(machineId=machineId))

        self.lg("Disable cloudspace (CS1) again, should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.disable(
                cloudspaceId=self.cloudspace_id, reason="test"
            )
        )

        self.lg("Delete cloudspace (CS1) should succeed")
        self.api.cloudapi.machines.delete(machineId=machineId)

    def test005_get_stop_start_destroy_deploy_vfw(self):
        """ OVC-056
        *Test case for test start stop move destroy virtual firewall.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Try to connect to vm (VM1), should succeed.
        #. Stop cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should fail.
        #. Start cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        #. Destroy cloudspace (CS1)'s vfw, should succeed.
        #. Deploy new vfw for cloudspace (CS1), should succeed.
        #. Try to connect to vm (VM1), should succeed.
        """
        self.lg("Create virtual machine (VM1)")
        machine_id = self.cloudapi_create_machine(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_id
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        machine_client = VMClient(machine_id)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

        self.lg("Stop cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.stopVFW(self.cloudspace_id)
        self.wait_for_status(
            "HALTED",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to connect to vm (VM1), should fail")
        with self.assertRaises(socket.error):
            VMClient(machine_id, timeout=1)

        self.lg("Start cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.startVFW(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        machine_client = VMClient(machine_id)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

        self.lg("Destroy cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.destroyVFW(self.cloudspace_id)
        self.wait_for_status(
            "VIRTUAL",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.cloudspace.getVFW(self.cloudspace_id)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("Deploy new vfw for cloudspace (CS1), should succeed")
        self.api.cloudbroker.cloudspace.deployVFW(self.cloudspace_id)
        self.wait_for_status(
            "DEPLOYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        machine_client = VMClient(machine_id)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

    def test006_move_vfw(self):
        """ OVC-057
        *Test case for test start stop move remove virtual firewall.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Move cloudspace (CS1)'s vfw to another node, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        #. Stop cloudspace (CS1)'s vfw, should succeed.
        #. Move cloudspace (CS1)'s vfw to another node, should succeed.
        #. Start cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        """
        vfw = self.api.cloudbroker.cloudspace.getVFW(self.cloudspace_id)

        self.lg("Create virtual machine (VM1)")
        machine_id = self.cloudapi_create_machine(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_id
        )

        self.lg("Move cloudspace (CS1)'s vfw to another node, should succeed")
        node_id = self.get_running_nodeId(except_nodeid=vfw["nid"])
        if not node_id:
            self.skipTest("No enabled nodes were found to move the VFW")

        self.api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
            self.cloudspace_id, node_id
        )
        vfw = self.api.cloudbroker.cloudspace.getVFW(self.cloudspace_id)
        self.assertEqual(vfw["nid"], node_id)
        self.wait_for_status(
            "RUNNING",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        machine_client = VMClient(machine_id)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

        self.lg("Stop cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.stopVFW(self.cloudspace_id)
        self.wait_for_status(
            "HALTED",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Move cloudspace (CS1)'s vfw to another node, should succeed")
        node_id = self.get_running_nodeId(except_nodeid=vfw["nid"])
        if not node_id:
            self.skipTest("No enabled nodes were found to move the VFW")

        self.api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
            self.cloudspace_id, node_id
        )
        vfw = self.api.cloudbroker.cloudspace.getVFW(self.cloudspace_id)
        self.assertEqual(vfw["nid"], node_id)

        self.lg("Start cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.startVFW(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        machine_client = VMClient(machine_id)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

    def test007_reset_vfw(self):
        """ OVC-058
        *Test case for test start stop move remove virtual firewall.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Execute script on routeros of cloudspace (CS1) to create portforward (PF1), should succeed.
        #. Try to connect to virtual machine (VM1) through PF1, should succeed.
        #. Reset cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to virtual machine (VM1) through PF1, should fail.
        #. Destroy cloudspace (CS1)'s vfw.
        #. Try to reset cloudspace (CS1)'s vfw, should fail.
        """
        self.lg("Create virtual machine (VM1)")
        machine_id = self.cloudapi_create_machine(self.cloudspace_id)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_id
        )

        self.lg(
            "Execute script on routeros of cloudspace (CS1) to create portforward (PF1), should succeed"
        )
        cloudspace_ip = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)[
            "publicipaddress"
        ]
        vm_ip = self.get_machine_ipaddress(machine_id)
        public_port = random.randint(30000, 60000)
        local_port = 22
        script = "/ip firewall nat add chain=dstnat action=dst-nat \
                 to-addresses={vm_ip} to-ports={local_port} protocol=tcp dst-address={cloudspace_ip} \
                 dst-port={public_port} comment=cloudbroker".format(
            vm_ip=vm_ip,
            cloudspace_ip=cloudspace_ip,
            public_port=public_port,
            local_port=local_port,
        )

        self.api.cloudapi.cloudspaces.executeRouterOSScript(
            self.cloudspace_id, script=script
        )

        self.lg("Try to connect to virtual machine (VM1) through PF1, should succeed")
        machine_client = VMClient(machine_id, port=public_port)
        stdin, stdout, stderr = machine_client.execute("uname")
        self.assertIn("Linux", stdout.read())

        self.lg("Reset cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.resetVFW(
            self.cloudspace_id, resettype="factory"
        )

        self.lg(
            "Try to connect to virtual machine (VM1) through portforward (PF1), should fail"
        )
        with self.assertRaises(socket.error):
            VMClient(machine_id, port=public_port, timeout=1)

        self.lg("Destroy cloudspace (CS1)'s vfw")
        self.api.cloudbroker.cloudspace.destroyVFW(self.cloudspace_id)

        self.lg("Try to reset cloudspace (CS1)'s vfw, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.cloudspace.resetVFW(
                self.cloudspace_id, resettype="factory"
            )
        self.assertEqual(e.exception.status_code, 400)

    def test007_distrbute_router_os_over_cpu_nodes(self):
        """ OVC-059
        *Test case for router os creation*

        **Test Scenario:**
        #. Check the number of the router os on all the available cpu node.
        #. Create new cloudspace (CS1).
        #. Check that the new cloudspace is created on the cpu node with smallest number of router os.

        """
        self.lg("Check the number of the router os on all the available cpu node")

        cb = j.clients.osis.getNamespace("cloudbroker")
        vcl = j.clients.osis.getNamespace("vfw")
        gid = j.application.whoAmI.gid
        stacks = cb.stack.list()

        stacks_list = []
        for stackId in stacks:
            stack = cb.stack.get(stackId)
            if stack.status != "ENABLED":
                continue

            referenceId = int(stack.referenceId)
            number_of_ros = vcl.virtualfirewall.count({"gid": gid, "nid": referenceId})
            stacks_list.append((referenceId, number_of_ros))

        min_ros_count = min(stacks_list, key=lambda tup: tup[1])[1]
        available_stacks = [
            stack[0] for stack in stacks_list if stack[1] == min_ros_count
        ]

        self.lg("Create new cloudspace")
        cloudspace_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )

        self.lg(
            "Check that the new cloudspace is created on the cpu node with smallest number of router os"
        )
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspace_id)
        self.assertIn(vfw["nid"], available_stacks)
