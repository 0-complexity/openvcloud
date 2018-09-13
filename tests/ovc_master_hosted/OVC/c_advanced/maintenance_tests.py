import unittest
from ....utils.utils import BasicACLTest, VMClient
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
import time
from JumpScale import j


class MaintenanceTests(BasicACLTest):
    def setUp(self):
        super(MaintenanceTests, self).setUp()
        self.default_setup()
        self.stackId = self.get_running_stackId()
        if not self.stackId:
            self.skipTest("[*] No running nodes ")

        ccl = j.clients.osis.getNamespace("cloudbroker")
        self.nodeId = ccl.stack.get(self.stackId).referenceId
        self.gridId = self.get_node_gid(self.stackId)

    def tearDown(self):
        if self.nodeId != -1:
            self.lg("Enable CPU1, should succeed")
            self.api.cloudbroker.node.enable(nid=self.nodeId, message="test")
            self.assertTrue(self.wait_for_node_status(self.nodeId, "ENABLED"))
        super(MaintenanceTests, self).tearDown()

    def wait_till_vm_move(self, vm_id, stackId, status="RUNNING", retry=300):
        """
        stackId: stackId that the vm will move from.
        status: status that need to be checked on after vm migration.
        """
        for _ in xrange(retry):
            time.sleep(2)
            vm = self.api.cloudbroker.machine.get(machineId=vm_id)
            if vm["stackId"] != stackId:
                break
            else:
                continue
        self.assertNotEqual(vm["stackId"], stackId, "vm didn't move to another stack")
        self.assertEqual(vm["status"], status, "vm is not %s" % status)

    def wait_till_vfw_move(self, cloudspaceId, vfw_node, retry=300):
        """
        vfw_node: old vfw's cpu-node name.
        """
        for _ in xrange(retry):
            time.sleep(2)
            vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
            if vfw["nodename"] != vfw_node:
                break
            else:
                continue
        self.assertNotEqual(
            vfw["nodename"], vfw_node, "vfw didn't move to another stack"
        )

    def wait_till_maintenance_done(self, nid, retry=300):
        vcl = j.clients.osis.getNamespace("vfw")
        for _ in xrange(retry):
            time.sleep(2)
            stack = self.api.models.stack.searchOne({"referenceId": str(nid)})
            vm_states = ["DESTROYED", "DELETED", "ERROR", "HALTED"]
            usedvms = self.api.models.vmachine.count(
            {
                "stackId": stack["id"],
                "status": {"$nin": vm_states},
            }
            )
            roscount = vcl.virtualfirewall.count({"gid": stack["gid"], "nid": nid})
            if not roscount and not usedvms:
                break
        else:
            raise RuntimeError("Putting node in maintenance took longer than expected")

    def test001_check_vm_ext_net_migration(self):
        """ OVC-052
        *Test case for checking vm migration in which it is attached to external network*

        **Test Scenario:**

        #. Create cloudspace (CS1), should succeed.
        #. Create a vm (VM1), should succeed.
        #. Attach VM1 to an external network.
        #. Get VM1's cpu-node (CPU1) and put it in maintenance (option "move vms"), should succeed.
        #. Make sure VM1 has been moved to another cpu-node.
        #. Try to move VM1 back to CPU1, should fail.
        #. Enable CPU1, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create a vm (VM1), should succeed.")
        vm_id = self.cloudbroker_create_machine(
            self.cloudspace_id, stackId=self.stackId
        )

        self.lg("Attach VM1 to an external network.")
        response = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm_id)
        self.assertTrue(response)

        self.lg(
            "Get VM1's cpu-node (CPU1) and put it in maintenance (option (move vms)), should succeed."
        )
        self.lg("Put node in maintenance with migrate all vms, should succeed")
        self.api.cloudbroker.node.maintenance(nid=self.nodeId, vmaction="move")
        self.wait_till_maintenance_done(self.nodeId)

        self.lg("Make sure VM1 has been moved to another cpu-node.")
        self.wait_till_vm_move(vm_id, self.stackId)
        self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))

        self.lg("Try to move VM1 back to CPU1, should fail.")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.machine.moveToDifferentComputeNode(
                machineId=vm_id, reason="test", targetStackId=self.stackId, force=False
            )
        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["move", "stop"])
    def test002_node_maintenance_migrateVMs(self, migrate_option):
        """ OVC-49
        *Test case for putting node in maintenance with action move or stop all vms.*

        **Test Scenario:**

        #. Create 3 VMs, should succeed.
        #. Leave one VM running, stop one, and pause another, should succeed.
        #. Put node in maintenance with migrate all vms, should succeed.
        #. Check if the 3 VMs have been migrated keeping their old state, should succeed.
        #. Wait until VM1's vfw be running.
        #. Check that the running VM is working well (option=move vms), should succeed.
        #. Enable the node back, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create 3 VMs, should succeed")
        machine_1_id = self.cloudbroker_create_machine(
            self.cloudspace_id, stackId=self.stackId
        )
        machine_2_id = self.cloudbroker_create_machine(
            self.cloudspace_id, stackId=self.stackId
        )
        machine_3_id = self.cloudbroker_create_machine(
            self.cloudspace_id, stackId=self.stackId
        )
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_1_id
        )
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_2_id
        )
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_3_id
        )

        self.lg("Leave one VM running, stop one, and pause another, should succeed.")
        stopped = self.api.cloudapi.machines.stop(machineId=machine_2_id)
        self.assertTrue(stopped)
        self.api.cloudapi.machines.pause(machineId=machine_3_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_3_id)["status"], "PAUSED"
        )

        self.lg("Put node in maintenance with migrate all vms, should succeed")
        self.api.cloudbroker.node.maintenance(nid=self.nodeId, vmaction=migrate_option)
        self.wait_till_maintenance_done(self.nodeId)

        self.lg(
            "Check if the 3 VMs have been migrated keeping their old state, should succeed"
        )
        if migrate_option == "move":
            self.wait_till_vm_move(machine_1_id, self.stackId, status="RUNNING")
            self.wait_till_vm_move(machine_2_id, self.stackId, status="HALTED")
            self.wait_till_vm_move(machine_3_id, self.stackId, status="PAUSED")
            self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))

            self.lg("Wait until VM1's vfw be running")
            self.wait_for_status(
                "RUNNING",
                self.api.cloudbroker.cloudspace.getVFW,
                cloudspaceId=self.cloudspace_id,
            )
            
            self.lg("Check that the running VM is working well, should succeed")
            machine_1_client = VMClient(machine_1_id)
            stdin, stdout, stderr = machine_1_client.execute("uname")
            self.assertIn("Linux", stdout.read())
        else:
            self.wait_for_status(
                "HALTED",
                self.api.cloudapi.machines.get,
                machineId=machine_1_id,
            )
            self.wait_for_status(
                "HALTED",
                self.api.cloudapi.machines.get,
                machineId=machine_2_id,
            )
            self.wait_for_status(
                "HALTED",
                self.api.cloudapi.machines.get,
                machineId=machine_3_id,
            )
            self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))

            self.lg(
                "Enable CPU1, should succeed and check that the vms are keeping their old state"
            )
            self.api.cloudbroker.node.enable(nid=self.nodeId, message="test")
            self.assertTrue(self.wait_for_node_status(self.nodeId, "ENABLED"))
            self.nodeId = -1  # prevent enabling the node in tearDown
            self.wait_for_status(
                "RUNNING",
                self.api.cloudapi.machines.get,
                machineId=machine_1_id,
            )
            self.wait_for_status(
                "HALTED",
                self.api.cloudapi.machines.get,
                machineId=machine_2_id,
            )
            self.wait_for_status(
                "HALTED",
                self.api.cloudapi.machines.get,
                machineId=machine_3_id,
            )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["move", "stop"])
    def test003_running_vfw_node_maintenance(self, migrate_option):
        """ OVC-053
        *Test case for migrating running VFW by putting node in maintenance with action move or stop all vms.*

        **Test Scenario:**

        #. Create cloud space and get its virtual firewall (VFW), should succeed.
        #. Put VFW's node (CPU1) in maintenance, should succeed.
        #. Make sure the running (VFW1) has been migrated to another cpu-node.
        #. Move VFW1 to CPU1, should fail.
        #. Stop VFW1, should succeed.
        #. Enable CPU1, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(
            "Create cloud space and get its virtual firewall (VFW), should succeed."
        )
        vfw1 = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=self.cloudspace_id)
        self.assertTrue(vfw1)
        self.nodeId = vfw1["nid"]

        osiscl = j.clients.osis.getByInstance("main")
        nodecl = j.clients.osis.getCategory(osiscl, "system", "node")
        nodes = nodecl.simpleSearch({})
        nodes = [node for node in nodes if "cpunode" in node["roles"]]

        self.lg("Put VFW's node (CPU1) in maintenance, should succeed.")
        self.api.cloudbroker.node.maintenance(nid=self.nodeId, vmaction=migrate_option)
        self.wait_till_maintenance_done(self.nodeId)

        if migrate_option == "move":
            self.lg(
                "Make sure the running (VFW1) has been migrated to another cpu-node."
            )
            self.wait_till_vfw_move(self.cloudspace_id, vfw1["nodename"])
            self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))

            self.lg("Move VFW1 to CPU1, should fail.")
            with self.assertRaises(HTTPError) as e:
                self.api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
                    cloudspaceId=self.cloudspace_id, targetNid=self.nodeId
                )
            self.lg("- expected error raised %s" % e.exception.status_code)
            self.assertEqual(e.exception.status_code, 400)

            self.lg("Stop VFW1, should succeed.")
            response = self.api.cloudbroker.cloudspace.stopVFW(
                cloudspaceId=self.cloudspace_id
            )
            self.assertTrue(response)
            self.wait_for_status(
                "HALTED",
                self.api.cloudbroker.cloudspace.getVFW,
                cloudspaceId=self.cloudspace_id,
            )
        else:
            self.lg("make sure VFW1 has been stopped")
            self.wait_for_status(
                "HALTED",
                self.api.cloudbroker.cloudspace.getVFW,
                cloudspaceId=self.cloudspace_id,
            )
            self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))
            self.lg("Enable CPU1, should succeed and check that the vfw is running")
            self.api.cloudbroker.node.enable(nid=self.nodeId, message="test")
            self.assertTrue(self.wait_for_node_status(self.nodeId, "ENABLED"))
            self.nodeId = -1  # prevent enabling the node in tearDown

            self.wait_for_status(
                "RUNNING",
                self.api.cloudbroker.cloudspace.getVFW,
                cloudspaceId=self.cloudspace_id,
            )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["move", "stop"])
    def test005_starting_vfw_node_maintenance(self, migrate_option):
        """ OVC-055
        *Test case for starting VFW after putting node in maintenance*

        **Test Scenario:**

        #. Create cloud space and stop its virtual firewall (VFW).
        #. Put VFW's node (CPU1) in maintenance, should succeed.
        #. Start VFW, and make sure it has been moved to another cpu-node.
        #. Enable CPU1, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create cloud space and stop its virtual firewall (VFW).")
        response = self.api.cloudbroker.cloudspace.stopVFW(
            cloudspaceId=self.cloudspace_id
        )
        self.assertTrue(response)
        self.wait_for_status(
            "HALTED",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )
        vfw1 = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=self.cloudspace_id)
        self.nodeId = vfw1["nid"]

        self.lg("Put VFW's node (CPU1) in maintenance, should succeed.")
        self.api.cloudbroker.node.maintenance(nid=self.nodeId, vmaction=migrate_option)
        self.wait_till_maintenance_done(self.nodeId)
        self.assertTrue(self.wait_for_node_status(self.nodeId, "MAINTENANCE"))

        self.lg("Start VFW, and make sure it has been moved to another cpu-node.")
        response = self.api.cloudbroker.cloudspace.startVFW(
            cloudspaceId=self.cloudspace_id
        )
        self.assertTrue(response)
        self.wait_for_status(
            "RUNNING",
            self.api.cloudbroker.cloudspace.getVFW,
            cloudspaceId=self.cloudspace_id,
        )
        self.wait_till_vfw_move(self.cloudspace_id, vfw1["nodename"])

        self.lg("%s ENDED" % self._testID)
