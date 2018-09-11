import unittest, random, uuid, socket
from multiprocessing import Process, Value
from ....utils.utils import BasicACLTest, VMClient
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
import time
import threading
import os, requests
import paramiko


class MachineTests(BasicACLTest):
    def setUp(self):
        super(MachineTests, self).setUp()
        self.default_setup()

    def test001_check_machines_networking(self):
        """ OVC-038
        *Test case for checking machines networking*

        **Test Scenario:**

        #. Create cloudspace CS1, should succeed.
        #. Create cloudspace CS2, should succeed.
        #. Create VM1 in cloudspace CS1.
        #. Create VM2 and VM3 in cloudspace CS2.
        #. From VM1 ping google, should succeed.
        #. From VM1 ping VM3, should fail.
        #. From VM2 ping VM3, should succeed.
        """

        self.lg("Create cloudspace CS1, should succeed")
        cloudspace_1_id = self.cloudspace_id

        self.lg("Create cloudspace CS2, should succeed")
        cloudspace_2_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )

        self.lg("Create VM1 in cloudspace CS1")
        machine_1_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_1_id)
        machine_1_ipaddress = self.get_machine_ipaddress(machine_1_id)
        self.assertTrue(machine_1_ipaddress)
        machine_1_client = VMClient(machine_1_id)

        self.lg("Create VM2 in cloudspace CS2")
        machine_2_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_2_id)
        machine_2_ipaddress = self.get_machine_ipaddress(machine_2_id)
        self.assertTrue(machine_2_ipaddress)
        machine_2_client = VMClient(machine_2_id)

        self.lg("Create VM3 in cloudspace CS2")
        machine_3_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_2_id)
        machine_3_ipaddress = self.get_machine_ipaddress(machine_3_id)
        self.assertTrue(machine_3_ipaddress)

        time.sleep(15)

        self.lg("From VM1 ping google, should succeed")
        stdin, stdout, stderr = machine_1_client.execute("ping -c3 8.8.8.8")
        self.assertIn("3 received", stdout.read())

        self.lg("From VM1 ping VM3 or VM2, should fail")
        if machine_1_ipaddress == machine_2_ipaddress:
            target_ip = machine_3_ipaddress
        else:
            target_ip = machine_2_ipaddress

        cmd = "ping -w3 {}".format(target_ip)
        stdin, stdout, stderr = machine_1_client.execute(cmd)
        self.assertIn(", 100% packet loss", stdout.read())

        self.lg("From VM2 ping VM3, should succeed")
        cmd = "ping -c3 {}".format(machine_3_ipaddress)
        stdin, stdout, stderr = machine_2_client.execute(cmd)
        self.assertIn("3 received", stdout.read())

    def test002_check_network_data_integrity(self):
        """ OVC-036
        *Test case for checking network data integrity through VMS*

        **Test Scenario:**

        #. Create a cloudspace CS1, should succeed.
        #. Create VM1 and VM2 inside CS1, should succeed.
        #. Create a file F1 inside VM1.
        #. From VM1 send F1 to VM2, should succeed.
        #. Check that F1 has been sent to vm2 without data loss.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create VM1 and VM2 inside CS1, should succeed")
        machine_1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        machine_2_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        machine_1_client = VMClient(machine_1_id)
        machine_2_client = VMClient(machine_2_id)

        self.lg("create a file F1 inside VM1")
        machine_1_client.execute('echo "helloWorld" > test.txt')

        self.lg("From VM1 send F1 to VM2, should succeed")
        self.send_file_from_vm_to_another(machine_1_client, machine_2_id, "test.txt")

        self.lg("Check that F1 has been sent to vm2 without data loss")
        stdin, stdout, stderr = machine_2_client.execute("cat test.txt")
        self.assertEqual("helloWorld", stdout.read().strip())

        self.lg("%s ENDED" % self._testID)

    def test003_check_connectivity_through_external_network(self):
        """ OVC-042
        *Test case for checking machine connectivity through external network*

        **Test Scenario:**

        #. Create a cloudspace CS1, should succeed
        #. Create VM1
        #. Attach VM1 to an external network, should succeed
        #. Assign IP to VM1's external netowrk interface, should succeed.
        #. Check if you can ping VM1 from outside, should succeed
        #. Check that you can connect to vm with new ip ,should succeed.

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create VM1,should succeed.")
        vm1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Attach VM1 to an external network, should succeed")
        reponse = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm1_id)
        self.assertTrue(reponse)

        self.lg("Assign IP to VM1's external netowrk interface, should succeed.")
        vm1_nics = self.api.cloudapi.machines.get(machineId=vm1_id)["interfaces"]
        vm1_nic = [x for x in vm1_nics if "externalnetworkId" in x["params"]][0]
        self.assertTrue(vm1_nic)
        vm1_ext_ip = vm1_nic["ipAddress"]
        vm1_client = VMClient(vm1_id)
        vm1_client.execute("ip a a %s dev ens6" % vm1_ext_ip, sudo=True)
        vm1_client.execute(
            "nohup bash -c 'ip l s dev ens6 up </dev/null >/dev/null 2>&1 & '",
            sudo=True,
        )

        self.lg("Check if you can ping VM1 from outside, should succeed")
        vm1_ext_ip = vm1_ext_ip[: vm1_ext_ip.find("/")]
        response = os.system("ping -c 1 %s" % vm1_ext_ip)
        self.assertFalse(response)

        self.lg("Check that you can connect to vm with new ip ,should succeed")
        vm1_client = VMClient(vm1_id, external_network=True)
        stdin, stdout, stderr = vm1_client.execute("ls /")
        self.assertIn("bin", stdout.read())

    # @unittest.skip('https://github.com/0-complexity/openvcloud/issues/1113')
    def test004_migrate_vm_in_middle_of_writing_file(self):
        """ OVC-039
        *Test case for checking data integrity after migrating vm in the middle of writing a file*

        **Test Scenario:**

        #. Create a cloudspace CS1, should succeed
        #. Create VM1, should succeed
        #. Write a big file FS1 on VM1
        #. Migrate VM1 in the middle of writing a file, should succeed
        #. Check if the file has been written correctly after vm live migration
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create VM1,should succeed.")
        vm1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Make sure that the bridge is created")
        hexNetworkID = "%04x" % self.get_cloudspace_network_id(self.cloudspace_id)
        vmnodeid = self.get_machine_nodeID(vm1_id)
        command = "ls /sys/class/net"  # All created bridges in this node
        result = self.execute_command_on_physical_node(command, vmnodeid)
        self.assertIn("space_" + hexNetworkID, result)

        self.lg("Write a big file FS1 on VM1")
        current_stackId = self.api.cloudbroker.machine.get(machineId=vm1_id)["stackId"]
        second_node = self.get_running_stackId(current_stackId)
        if not second_node:
            self.skipTest("[*] No running nodes ")
        vm1_client = VMClient(vm1_id)
        cmd = "yes 'Some text' | head -n 200000000 > largefile.txt"
        t = threading.Thread(target=vm1_client.execute, args=(cmd,))
        t.start()
        time.sleep(7)

        self.lg("Migrate VM1 to another node, should succeed.")
        self.api.cloudbroker.machine.moveToDifferentComputeNode(
            machineId=vm1_id, reason="test", targetStackId=second_node, force=False
        )
        vm1 = self.api.cloudbroker.machine.get(machineId=vm1_id)
        self.assertEqual(vm1["stackId"], second_node)

        self.lg("Make sure that VM1 is running.")
        self.assertEqual(vm1["status"], "RUNNING")
        t.join()
        vm1_client = VMClient(vm1_id)
        stdin, stdout, stderr = vm1_client.execute("ls /")
        self.assertIn("bin", stdout.read())

        self.lg("Check if the file has been written correctly after vm live migration")
        stdin, stdout, stderr = vm1_client.execute(
            'md5sum largefile.txt | cut -d " " -f 1'
        )
        self.assertEqual(stdout.read().strip(), "cd96e05cf2a42e587c78544d19145a7e")

        self.lg("Check the bridge was removed")
        command = "ls /sys/class/net"  # All created bridges in this node
        result = self.execute_command_on_physical_node(command, vmnodeid)
        self.assertNotIn("space_" + hexNetworkID, result)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["Linux", "Windows"])
    def test005_cheching_vm_specs_after_rebooting(self, image_type):
        """ OVC-028
        *Test case for checking VM's ip and credentials after rebooting*

        **Test Scenario:**

        #. Create virtual machine VM1 with windows image.
        #. Get machine VM1 info, should succeed.
        #. Reboot VM1, should succeed.
        #. Get machine VM1 info, should succeed.
        #. Check if VM1's ip is the same as before rebooting.
        #. Check if VM1's credentials are the same as well.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- Create virtual machine VM1 with {} image".format(image_type))
        target_images = [
            x["id"] for x in self.api.cloudapi.images.list() if x["type"] == image_type
        ]

        if not target_images:
            self.skipTest("No image with type {} is avalilable".format(image_type))

        selected_image_id = random.choice(target_images)

        machineId = self.cloudapi_create_machine(
            self.cloudspace_id,
            self.account_owner_api,
            image_id=selected_image_id,
            disksize=50,
        )

        self.lg("2- Get machine VM1 info, should succeed")
        machine_info_before_reboot = self.api.cloudapi.machines.get(machineId=machineId)

        self.lg("3- Reboot VM1, should succeed")
        self.assertTrue(self.api.cloudapi.machines.reboot(machineId=machineId))

        self.lg("4- Get machine VM1 info, should succeed")
        machine_info_after_reboot = self.api.cloudapi.machines.get(machineId=machineId)

        self.lg("5- Check if VM1's ip is the same as before rebooting")
        self.assertEqual(
            machine_info_before_reboot["interfaces"][0]["ipAddress"],
            machine_info_after_reboot["interfaces"][0]["ipAddress"],
        )

        self.lg("6- Check if VM1's credentials are the same as well")
        self.assertEqual(
            machine_info_before_reboot["accounts"][0]["login"],
            machine_info_after_reboot["accounts"][0]["login"],
        )

        self.assertEqual(
            machine_info_before_reboot["accounts"][0]["password"],
            machine_info_after_reboot["accounts"][0]["password"],
        )

        self.lg("%s ENDED" % self._testID)

    def test006_attach_same_disk_to_two_vms(self):
        """ OVC-024
        *Test case for attaching same disk to two different vms*

        **Test Scenario:**

        #. Create VM1 and VM2.
        #. Create disk DS1.
        #. Attach DS1 to VM1, should succeed.
        #. Attach DS1 to VM2, should fail.
        #. Detach DS1 from VM2, should fail.
        #. Delete disk after detaching it, should succeed
        """
        # Note: try this scenario for data and boot disks

        self.lg("%s STARTED" % self._testID)

        self.lg("Create VM1 and VM2")
        VM1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        VM2_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg(" Create disk DS1.")
        disk_id = self.create_disk(self.account_id)
        self.assertTrue(disk_id)

        self.lg("Attach DS1 to VM1, should succeed.")
        response = self.api.cloudapi.machines.attachDisk(
            machineId=VM1_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg("Attach DS1 to VM2, should fail.")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.attachDisk(machineId=VM2_id, diskId=disk_id)

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("Delete disk after detaching it, should succeed")
        response = self.api.cloudapi.disks.delete(diskId=disk_id, detach=True)
        self.assertTrue(response)

        self.lg("%s ENDED" % self._testID)

    def test007_detach_boot_disks(self):
        """ OVC-035
        * Test case for swapping vms boot disks.

        **Test Scenario:**

        #. Create virtual machines (VM1).
        #. Stop VM1, should succeed.
        #. Detach VM1's boot disk, should fail.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create virtual machines (VM1)")
        machine_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Stop VM1, should succeed")
        self.api.cloudapi.machines.stop(machineId=machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_id)["status"], "HALTED"
        )

        self.lg("Detach VM1's boot disk, should fail")
        disk_id = self.api.cloudapi.machines.get(machineId=machine_id)["disks"][0]["id"]

        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.detachDisk(machineId=machine_id, diskId=disk_id)

        self.assertTrue(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    # @unittest.skip('https://github.com/0-complexity/openvcloud/issues/1113')
    def test009_restart_vm_after_migration(self):
        """ OVC_037
        *Test case for checking VM status after restarting it after migration*

        **Test Scenario:**

        #. Create a cloudspace CS1, should succeed.
        #. Create VM1,should succeed.
        #. Migrate VM1 to another node, should succeed.
        #. Make sure that VM1 is running.
        #. Restart VM1 and make sure it is still running.

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create VM1,should succeed.")
        vm1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        self.assertTrue(vm1_id)
        current_stackId = self.api.cloudbroker.machine.get(machineId=vm1_id)["stackId"]

        self.lg("Migrate VM1 to another node, should succeed.")
        second_node = self.get_running_stackId(current_stackId)
        if not second_node:
            self.skipTest("[*] Not enough running nodes ")
        self.api.cloudbroker.machine.moveToDifferentComputeNode(
            machineId=vm1_id, reason="test", targetStackId=second_node, force=True
        )
        self.assertEqual(
            self.api.cloudbroker.machine.get(machineId=vm1_id)["stackId"], second_node
        )

        self.lg("Make sure that VM1 is running.")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=vm1_id)["status"], "RUNNING"
        )
        vm1_client = VMClient(vm1_id)
        stdin, stdout, stderr = vm1_client.execute("ls /")
        self.assertIn("bin", stdout.read())

        self.lg("Restart VM1 and make sure it is still running.")
        self.api.cloudapi.machines.reboot(machineId=vm1_id)
        time.sleep(2)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=vm1_id)["status"], "RUNNING"
        )
        vm1_client = VMClient(vm1_id)
        stdin, stdout, stderr = vm1_client.execute("ls /")
        self.assertIn("bin", stdout.read())

        self.lg("%s ENDED" % self._testID)

    def test010_check_cloned_vm(self):
        """ OVC-029
        *Test case for checking cloned VM ip, portforwards and credentials*

        **Test Scenario:**

        #. Create (VM1), should succeed.
        #. Take a snapshot (SS0) for (VM1).
        #. Write file (F1) on (VM1).
        #. Stop (VM1), should succeed.
        #. Clone VM1 as (VM2_C), should succeed.
        #. Check that the cloned vm has one boot disk and one metadata disk.
        #. Start (VM1), should succeed
        #. Make sure VM2_C got a new ip.
        #. Make sure no portforwards have been created.
        #. Check that file (F1) exists.
        #. Rollback (VM2_C) to snapshot (SS1), should fail.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create (VM1), should succeed")
        machineId = self.cloudapi_create_machine(self.cloudspace_id)
        machine_1_ipaddress = self.get_machine_ipaddress(machineId)
        self.assertTrue(machine_1_ipaddress)

        self.lg("Take a snapshot (SS0) for (VM1)")
        snapshotId = self.api.cloudapi.machines.snapshot(
            machineId=machineId, name="test-snapshot"
        )
        snapshotEpoch = self.api.cloudapi.machines.listSnapshots(machineId=machineId)[
            0
        ]["epoch"]

        self.lg("Write file to (VM1)")
        machine_1_client = VMClient(machineId)
        machine_1_client.execute("touch helloWorld.txt")

        self.lg("Stop (VM1), should succeed")
        self.api.cloudapi.machines.stop(machineId=machineId)

        self.lg("Clone VM1 as (VM2_C), should succeed")
        cloned_vm_id = self.api.cloudapi.machines.clone(
            machineId=machineId, name="test"
        )
        cloned_machine_ipaddress = self.get_machine_ipaddress(cloned_vm_id)
        self.assertTrue(cloned_machine_ipaddress)

        self.lg("Check that the cloned vm has one boot disk and one metadata disk")
        cloned_machine_info = self.api.cloudapi.machines.get(machineId=cloned_vm_id)
        self.assertEqual(len(cloned_machine_info["disks"]), 2)
        self.assertEqual(
            len([x for x in cloned_machine_info["disks"] if x["type"] == "B"]), 1
        )
        self.assertEqual(
            len([x for x in cloned_machine_info["disks"] if x["type"] == "M"]), 1
        )

        self.lg("Start (VM1), should succeed")
        self.api.cloudapi.machines.start(machineId=machineId)

        self.lg("Make sure VM2_C got a new ip")
        self.assertNotEqual(machine_1_ipaddress, cloned_machine_ipaddress)

        self.lg("Make sure no portforwards have been created")
        portforwarding = self.api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=cloned_vm_id
        )
        self.assertEqual(portforwarding, [])

        self.lg("Check that file (F1) exists")
        cloned_machine_client = VMClient(cloned_vm_id)
        stdin, stdout, stderr = cloned_machine_client.execute(
            "ls | grep helloWorld.txt"
        )
        self.assertIn("helloWorld.txt", stdout.read())

        self.lg("Rollback (VM2_C) to snapshot (SS1), shoud fail")
        snapshots = self.api.cloudapi.machines.listSnapshots(machineId=cloned_vm_id)
        self.assertEqual(snapshots, [])

        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.rollbackSnapshot(
                machineId=cloned_vm_id, epoch=snapshotEpoch
            )

    # @unittest.skip('https://github.com/0-complexity/openvcloud/issues/1061')
    def test011_memory_size_after_attaching_external_network(self):
        """ OVC-043
        *Test case for memory size after attaching external network*

        **Test Scenario:**

        #. Create virtual machine (VM1), should succeed.
        #. Attach external network to virtual machine (VM1), should succeed.
        #. Add new disk (DS1), should succeed.
        #. Attach disk (DS1) to virtual machine (VM1), should succeed.
        #. Detach external network from virtual machine (VM1), should succeed.
        #. Stop virtual machine (VM1), should succeed.
        #. Resize virtual machine (VM1), should succeed.
        #. Start virtual machine (VM1), should succeed.
        #. Check that virtual machine (VM1) is sized with right size in MB unit.
        """

        self.lg("Create virtual machine (VM1), should succeed")
        images = self.api.cloudapi.images.list()
        image_id = [x["id"] for x in images if "Ubuntu" in x["name"]]

        if not image_id:
            self.skipTest("No Ubuntu image was found in the environment")

        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, image_id=image_id[0]
        )
        machine_info = self.api.cloudapi.machines.get(machineId=machine_id)

        self.lg("Attach external network to virtual machine (VM1), should succeed")
        response = self.api.cloudbroker.machine.attachExternalNetwork(
            machineId=machine_id
        )
        self.assertTrue(response)

        self.lg("Create disk (DS1)")
        disk_id = self.create_disk(self.account_id)
        self.assertTrue(disk_id)

        self.lg("Attach disk (DS1) to virtual machine (VM1), should succeed")
        response = self.api.cloudapi.machines.attachDisk(
            machineId=machine_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg("Detach external network from virtual machine (VM1), should succeed")
        response = self.api.cloudapi.machines.detachExternalNetwork(
            machineId=machine_id
        )
        self.assertTrue(response)

        self.lg("Stop virtual machine (VM1), should succeed")
        response = self.api.cloudapi.machines.stop(machineId=machine_id)
        self.assertTrue(response)

        self.wait_for_status(
            "HALTED", self.api.cloudapi.machines.get, machineId=machine_id
        )

        time.sleep(10)

        self.lg("Resize virtual machine (VM1), should succeed")
        available_sizes = range(1, 7)
        current_size_id = machine_info["sizeid"]
        available_sizes.remove(current_size_id)
        new_size_id = random.choice(available_sizes)
        response = self.api.cloudapi.machines.resize(
            machineId=machine_id, sizeId=new_size_id
        )
        self.assertTrue(response)

        time.sleep(10)

        self.lg("Start virtual machine (VM1), should succeed")
        response = self.api.cloudapi.machines.start(machineId=machine_id)
        self.assertTrue(response)

        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_id
        )

        self.lg("Check that virtual machine (VM1) is sized with right size in MB unit")
        vm_client = VMClient(machine_id)
        stdin, stdout, stderr = vm_client.execute("free -m | grep Mem")
        machine_memory = int(stdout.read().split()[1])
        expected_machine_memory = [
            x["memory"]
            for x in self.api.cloudapi.sizes.list(location=self.location)
            if x["id"] == new_size_id
        ][0]
        self.assertAlmostEqual(
            machine_memory,
            expected_machine_memory,
            delta=(0.1 * expected_machine_memory),
        )
        self.lg("%s ENDED" % self._testID)

    def test012_check_disk_iops_limit(self):
        """ OVC-046
        *Test case for checking cloned VM ip, portforwards and credentials*

        **Test Scenario:**

        #. Create virtual machine (VM1), should succeed.
        #. Attach data disk (DD1) to VM1 and set MaxIOPS to iops1.
        #. Run fio on DD1, iops should be less than iops1.
        #. Change DD1's MaxIOPS limit to iops2 which is double iops1.
        #. Run fio on DD1 again, iops should be between iops1 and iops2.
        """
        self.lg("%s STARTED" % self._testID)

        def get_iops(vm1_client, run_name):
            fio_cmd = (
                "fio --ioengine=libaio --group_reporting --direct=1 --filename=/dev/vdb "
                "--runtime=30 --readwrite=rw --rwmixwrite=5 --size=500M --name=test{0} "
                "--output={0}".format(run_name)
            )
            vm1_client.execute(fio_cmd, sudo=True)

            stdin, stdout, stderr = vm1_client.execute(
                "cat %s | grep -o 'iops=[0-9]\{1,\}' | cut -d '=' -f 2" % run_name
            )
            iops_list = stdout.read().split()
            return iops_list

        self.lg("Create virtual machine (VM1), should succeed.")
        images = self.api.cloudapi.images.list()
        image_id = [i["id"] for i in images if "Ubuntu" in i["name"]]
        if not image_id:
            self.skipTest("No Ubuntu image found")
        vm1_id = self.cloudapi_create_machine(self.cloudspace_id, image_id=image_id[0])
        vm1_ip = self.get_machine_ipaddress(vm1_id)
        self.assertTrue(vm1_ip)

        self.lg("Attach data disk (DD1) to VM1 and set MaxIOPS to iops1.")
        maxiops = 500
        disk_id = self.create_disk(self.account_id, maxiops=maxiops)
        response = self.api.cloudapi.machines.attachDisk(
            machineId=vm1_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg("Run fio on DD1, iops should be less than iops1.")
        vm1_client = VMClient(vm1_id)
        vm1_client.execute("apt-get update", sudo=True)
        vm1_client.execute("apt-get install fio -y", sudo=True)
        iops_list = get_iops(vm1_client, "b1")
        self.assertFalse([True for i in iops_list if int(i) > maxiops])

        self.lg("Change DD1's MaxIOPS limit to iops2 which is double iops1.")
        response = self.api.cloudapi.disks.limitIO(diskId=disk_id, iops=2 * maxiops)
        self.assertTrue(response)

        self.lg("Run fio on DD1 again, iops should be between iops1 and iops2.")
        iops_list = get_iops(vm1_client, "b2")
        self.assertTrue([True for i in iops_list if maxiops < int(i) < 2 * maxiops])

        self.lg("%s ENDED" % self._testID)

    def test013_check_IP_conflict(self):
        """ OVC-047
        *Test case for checking machine connectivity through external network*

        **Test Scenario:**

        #. Create cloudspace (CS1), should succeed.
        #. Create two virtual machines (VM1) & (VM2) in cloudspace (CS1),should succeed.
        #. Attach (VM1) & (VM2) to external networks (EN1), should succeed.
        #. Assign IPs to (VM1) and (VM2) external network's interfaces, should succeed.
        #. Check if (VM1) and (VM2) can ping google.com, should succeed.
        #. Check if (VM1) and (VM2) can ping external network (EN1)'s gateway ip, should succeed.
        #. Delete (VM2) external network ip, and give it the same ip of (VM1).
        #. Check that (VM1) still can work normally, should succeed.
        #. Check that you can't connect to (VM2) with it's new external network ip, should succeed.
        #. Delete (VM1) external network ip, and give it the same ip of (CS1).
        #. Check that you can't connect to VM1 with it's new ext network ip, should succeed.
        """

        self.lg("%s STARTED" % self._testID)

        self.lg(
            "Create two virtual machines (VM1) & (VM2) in cloudspace (CS1),should succeed"
        )
        vm1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        vm2_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        vm2_password = self.api.cloudapi.machines.get(machineId=vm2_id)["accounts"][0][
            "password"
        ]

        self.lg("Attach (VM1) & (VM2) to external networks (EN1), should succeed")
        response = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm1_id)
        self.assertTrue(response)

        reponse = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm2_id)
        self.assertTrue(reponse)

        self.lg(
            "Assign IPs to (VM1) and (VM2) external network's interfaces, should succeed"
        )

        vm1_ext_ip, ext_interface_name1 = self.assign_IP_to_vm_external_netowrk(vm1_id)
        vm2_ext_ip, ext_interface_name2 = self.assign_IP_to_vm_external_netowrk(vm2_id)

        vm_nics = self.api.cloudapi.machines.get(machineId=vm1_id)["interfaces"]
        params = [x for x in vm_nics if "externalnetworkId" in x["params"]][0]["params"]
        gateway_ip = params[params.find(":") + 1 : params.find(" ")]

        vm_1_ext_client = VMClient(vm1_id, external_network=True)
        vm_2_ext_client = VMClient(vm2_id, external_network=True)

        self.lg("Check if (VM1) and (VM2) can ping google.com, should succeed")
        self.assertIn(
            ", 0% packet loss", vm_1_ext_client.execute("ping -c 1 8.8.8.8")[1].read()
        )
        self.assertIn(
            ", 0% packet loss", vm_2_ext_client.execute("ping -c 1 8.8.8.8")[1].read()
        )

        self.lg(
            "Check if (VM1) and (VM2) can ping external network (EN1)'s gateway ip, should succeed"
        )
        self.assertIn(
            ", 0% packet loss",
            vm_1_ext_client.execute("ping -c 1 {}".format(gateway_ip))[1].read(),
        )
        self.assertIn(
            ", 0% packet loss",
            vm_2_ext_client.execute("ping -c 1 {}".format(gateway_ip))[1].read(),
        )

        self.lg("Delete (VM2) external network ip, and give it the same ip of (VM1)")
        vm_2_ext_client.execute(
            "ip a d {} dev {}".format(vm2_ext_ip, ext_interface_name2),
            sudo=True,
            wait=False,
        )
        vm_2_client = VMClient(vm2_id)
        vm_2_client.execute(
            "ip a a {} dev {}".format(vm1_ext_ip, ext_interface_name2), sudo=True
        )
        vm_2_client.execute(
            "nohup bash -c 'ip l s dev {} up </dev/null >/dev/null 2>&1 & '".format(
                ext_interface_name2
            ),
            sudo=True,
            wait=False,
        )

        self.lg("Check that (VM1) still can work normally, should succeed")
        self.assertIn(
            ", 0% packet loss",
            vm_1_ext_client.execute("ping -c 1 {}".format(gateway_ip))[1].read(),
        )

        self.lg(
            "Check that you can't connect to (VM2) with it's new external network ip, should succeed"
        )
        with self.assertRaises(paramiko.AuthenticationException):
            VMClient(vm2_id, ip=vm1_ext_ip, external_network=True, timeout=1)

        self.lg("Delete (VM1) external network ip, and give it the same ip of (CS1)")
        cs_ip = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)["publicipaddress"]
        vm_1_ext_client.execute(
            "ip a d {} dev {}".format(vm1_ext_ip, ext_interface_name1),
            sudo=True,
            wait=False,
        )
        vm_1_client = VMClient(vm1_id)
        vm_1_client.execute(
            "ip a a {} dev {}".format(cs_ip, ext_interface_name1), sudo=True
        )
        vm_1_client.execute(
            "nohup bash -c 'ip l s dev {} up </dev/null >/dev/null 2>&1 & '".format(
                ext_interface_name1
            ),
            sudo=True,
            wait=False,
        )

        self.lg(
            "Check that you can't connect to VM1 with it's new ext network ip, should succeed"
        )
        with self.assertRaises(socket.error):
            VMClient(vm1_id, ip=cs_ip, external_network=True, timeout=1)
        self.lg("%s ENDED" % self._testID)

    def test016_resize_disk_online(self):
        """ OVC-050
        *Test case for resizing disk online*
        **Test Scenario:**

        #. Create virtual machine (VM1), should succeeed
        #. Attach data disk (DS1) with size (S1), should succeed
        #. Resize DS1 to S2 (>S1), should succeed
        #. Make sure DS1's size has been changed on the vm itself
        #. Resize VM1's metadata disk, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create virtual machine (VM1), should succeeed")
        vm1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Attach data disk (DS1) with size (S1), should succeed")
        s1 = random.randint(10, 50)
        disk_id = self.create_disk(self.account_id, size=s1)
        self.assertTrue(disk_id)
        response = self.api.cloudapi.machines.attachDisk(
            machineId=vm1_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg("Resize DS1 to S2, should succeed")
        self.api.cloudapi.disks.resize(diskId=disk_id, size=s1 + 1)

        self.lg("Make sure DS1's size has been changed on the vm itself")
        vm1_client = VMClient(vm1_id)
        stdin, stdout, stderr = vm1_client.execute(
            "lsblk | grep vdb | awk '{print $4}'", sudo=True
        )
        self.assertIn(str(s1 + 1), stdout.read())

        self.lg("Resize VM1's metadata disk, should fail")
        vm1 = self.api.cloudapi.machines.get(vm1_id)
        meta_disk_id = [d["id"] for d in vm1["disks"] if d["type"] == "M"][0]
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.resize(diskId=meta_disk_id, size=s1)
        self.lg("- expected error raised %s" % e.exception.msg)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    def test017_concurrent_create_machine_with_account_resourcelimit(self):
        """ OVC-62
        *Test case for creating machines concurrently with resource limiting, meant to trigger double spending*

        **Test Scenario:**

        #. Create machines concurrently that just have enough resources to be created.
        #. Check if only one machine was created, if more, double spending occurred.
        """

        # create acc/cloudspace with limits on account
        self.lg("Creating account")
        account_name = str(uuid.uuid4()).replace("-", "")[0:10]
        account_id = self.cloudbroker_account_create(
            name=account_name,
            username=self.username,
            email=self.email,
            maxCPUCapacity=2,
            maxMemoryCapacity=512,
            maxVDiskCapacity=10,
        )

        self.lg("Creating cloudspace")
        cloudspace_id = self.cloudapi_cloudspace_create(
            account_id=account_id, location=self.location, access=self.username
        )

        data = {
            "cloudspace_id": cloudspace_id,
            "memory": 512,
            "vcpus": 2,
            "disksize": 10,
        }

        procs = []

        from multiprocessing import Process, Value

        created_machines = Value("i", 0, lock=True)
        for _ in range(5):
            p = Process(
                target=self._concurrent_create_machine,
                args=(created_machines,),
                kwargs=data,
            )
            procs.append(p)

        self.lg("Requesting creation of VMs concurrently")
        for p in procs:
            p.start()

        for p in procs:
            p.join()

        self.lg("Checking created VMs")
        self.assertEqual(
            1,
            created_machines.value,
            "Only 1 VM should have been created, found %s" % str(created_machines),
        )

    def test018_concurrent_create_machine_with_cloudspace_resourcelimit(self):
        """ OVC-63
        *Test case for creating machines concurrently with resource limiting, meant to trigger double spending*

        **Test Scenario:**

        #. Create machines concurrently that just have enough resources to be created.
        #. Check if only one machine was created, if more, double spending occurred.
        """

        # create acc/cloudspace with limits on cloudspace
        self.lg("Creating account")
        account_name = str(uuid.uuid4()).replace("-", "")[0:10]
        account_id = self.cloudbroker_account_create(
            name=account_name, username=self.username, email=self.email
        )

        self.lg("Creating cloudspace")
        cloudspace_id = self.cloudapi_cloudspace_create(
            account_id=account_id,
            location=self.location,
            access=self.username,
            maxCPUCapacity=2,
            maxMemoryCapacity=512,
            maxDiskCapacity=10,
        )

        data = {
            "cloudspace_id": cloudspace_id,
            "memory": 512,
            "vcpus": 2,
            "disksize": 10,
        }

        procs = []

        created_machines = Value("i", 0, lock=True)
        for _ in range(5):
            p = Process(
                target=self._concurrent_create_machine,
                args=(created_machines,),
                kwargs=data,
            )
            procs.append(p)

        self.lg("Requesting creation of VMs concurrently")
        for p in procs:
            p.start()

        for p in procs:
            p.join()

        self.lg("Checking created VMs")
        self.assertEqual(
            1,
            created_machines.value,
            "Only 1 VM should have been created, found %s" % str(created_machines),
        )

    def _concurrent_create_machine(self, created_machines, **kwargs):
        try:
            machine_id = self.cloudapi_create_machine(**kwargs)
        except HTTPError as err:
            if err.status_code == 400:
                return
            raise

        self.api.cloudapi.machines.get(machine_id)
        with created_machines.get_lock():
            created_machines.value += 1

    def test019_machine_attach_newly_created_external_network(self):
        """ OVC-66
        *Test case for attaching a virtual machine to a newly created external network*

        **Test Scenario:**

        #. Create machine, should succed.
        #. Create external network, should succeed.
        #. Attach new external network to the machine, should succeed.
        #. Detach new external network, should succeed.
        #. Remove new external network, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create machine, should succeed.")
        vm_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Create external network, should succeed")
        external_network_id = self.create_external_network()
        try:
            self.lg("Attach new external network to the machine, should succeed")
            reponse = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm_id, externalNetworkId=external_network_id)
            self.assertTrue(reponse)

            self.lg("Detach new external network, should succeed")
            reponse = self.api.cloudbroker.machine.detachExternalNetwork(machineId=vm_id, externalNetworkId=external_network_id)
            self.assertTrue(reponse)
        finally:
            self.lg("Remove new external network, should succeed")
            self.api.cloudbroker.iaas.deleteExternalNetwork(external_network_id)

        self.lg("%s ENDED" % self._testID)

    def test020_delete_external_network_used_by_machine(self):
        """ OVC-67
        *Test case for deleting an external network that is used by a machine*

        **Test Scenario:**

        #. Create external network, should succeed.
        #. Create machine, should succeed.
        #. Attach new external network to the machine, should succeed.
        #. Delete new external network, should fail.
        #. Delete created machine, should succeed.
        #. Delete new external network, should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create external network, should succeed")
        external_network_id = self.create_external_network()
        try:
            self.lg("Create machine, should succeed")
            vm_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

            self.lg("Attach new external network to the machine, should succeed")
            reponse = self.api.cloudbroker.machine.attachExternalNetwork(machineId=vm_id, externalNetworkId=external_network_id)
            self.assertTrue(reponse)

            self.lg("Delete new external network, should fail")
            with self.assertRaises(HTTPError) as e:
                self.api.cloudbroker.iaas.deleteExternalNetwork(external_network_id)
            self.assertEqual(e.exception.status_code, 409)

            self.lg("Delete created machine, should succeed")
            self.api.cloudapi.machines.delete(machineId=vm_id, permanently=True)
        finally:
            self.lg("Delete new external network, should succeed")
            self.api.cloudbroker.iaas.deleteExternalNetwork(external_network_id)

        self.lg("%s ENDED" % self._testID)

    def test021_delete_external_network_used_by_cloudspace(self):
        """ OVC-68
        *Test case for deleting an external network that is used by a cloudspace*

        **Test Scenario:**

        #. Getting external network of default Cloud Space, should succeed
        #. Delete Cloud Space's external network, should fail.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Getting external network of default Cloud Space, should succeed")
        external_network_id = self.api.models.cloudspace.get(self.cloudspace_id).externalnetworkId

        self.lg("Delete Cloud Space's external network, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.iaas.deleteExternalNetwork(external_network_id)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("%s ENDED" % self._testID)

