import unittest
from nose_parameterized import parameterized
from ....utils.utils import BasicACLTest
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
import random, uuid


class ExtendedTests(BasicACLTest):
    def setUp(self):
        super(ExtendedTests, self).setUp()
        self.default_setup()

    @parameterized.expand(["Ubuntu 16.04 x64"])
    def test001_create_vmachine_with_all_disks(self, image_name):
        """ OVC-013
        *Test case for create machine with Linux image available.*

        **Test Scenario:**

        #. validate the image is exists, should succeed
        #. get all available sizes to use, should succeed
        #. create machine using given image with specific size and all available disk sizes, should succeed
        #. check if disks are in correct state ASSIGNED
        #. delete vm 
        #. check if disks are in coorect state DELETED
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- validate the image is exists, should succeed")
        images = self.api.cloudapi.images.list()
        self.assertIn(
            image_name,
            [image["name"] for image in images],
            "Image [%s] not found in the environment available images" % image_name,
        )
        image = [image for image in images if image["name"] == image_name][0]

        self.lg("2- get all available sizes to use, should succeed")
        sizes = self.api.cloudapi.sizes.list(cloudspaceId=self.cloudspace_id)
        self.lg("- using image [%s]" % image_name)
        basic_sizes = [512, 1024, 4096, 8192, 16384, 2048]
        random_sizes = random.sample(basic_sizes, 3)
        for size in sizes:
            if size["memory"] not in random_sizes:
                continue
            self.lg(
                "- using image [%s] with memory size [%s]"
                % (image_name, size["memory"])
            )

            if len(size["disks"]) < 3:
                sample = len(size["disks"])
            else:
                sample = 3

            random_disks = random.sample(size["disks"], sample)

            for disk in random_disks:
                self.lg(
                    "- using image [%s] with memory size [%s] with disk "
                    "[%s]" % (image_name, size["memory"], disk)
                )
                machine_id = self.cloudapi_create_machine(
                    cloudspace_id=self.cloudspace_id,
                    size_id=size["id"],
                    image_id=image["id"],
                    disksize=disk,
                )
                self.lg("Make sure disks are in correct state")
                machine = self.api.cloudapi.machines.get(machine_id)
                m_disks = machine["disks"]
                for disk in m_disks:
                    self.assertEqual(
                        self.api.cloudapi.disks.get(disk["id"])["status"], "ASSIGNED"
                    )

                self.lg(
                    "- done using image [%s] with memory size [%s] with disk "
                    "[%s]" % (image_name, size["memory"], disk)
                )
                self.lg(
                    "- delete machine to free environment resources, should succeed"
                )
                self.api.cloudapi.machines.delete(machineId=machine_id)

                self.lg("Make sure disks are in correct state")
                for disk in m_disks:
                    self.assertEqual(
                        self.api.cloudapi.disks.get(disk["id"])["status"], "DELETED"
                    )

        self.lg("%s ENDED" % self._testID)

    def test003_create_vmachine_clone_with_empty_name(self):
        """ OVC-021
        *Test case for create vmachine/clone with empty name.*

        **Test Scenario:**

        #. Try to create machine with empty name, should fail
        #. Create normal machine with valid name, should succeed
        #. Stop the created machine to be able to clone it, should succeed
        #. Try to clone created machine with empty name, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- Try to create machine with empty name, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.create(
                cloudspaceId=self.cloudspace_id,
                name="",
                sizeId=self.get_size(self.cloudspace_id)["id"],
                imageId=self.get_image()["id"],
                disksize=10,
            )
        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("2- Create normal machine with valid name, should succeed")
        machine_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)
        self.machine_ids = [machine_id]

        self.lg("3- Stop the created machine to be able to clone it, should succeed")
        self.api.cloudapi.machines.stop(machineId=machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_id)["status"], "HALTED"
        )

        self.lg("4- Try to clone created machine with empty name, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.clone(machineId=machine_id, name="")

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["D", "B"])
    def test004_disk_create_delete(self, disk_type):
        """ OVC-022
        *Test case for creating and deleting disks*

        **Test Scenario:**

        #. Create a data disk DS1, should succeed.
        #. Make sure disk is in CREATED state
        #. List the data disks, DS1 should be found.
        #. List the Boot disks, DS1 shouldn't be found
        #. Delete DS1, should succeed.
        #. Make sure disk is in DELETED STATE
        #. List the disks, DS1 shouldn't be there.
        #. Repeat the above steps for a boot Disk
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(" Create a %s disk DS1, should succeed" % disk_type)
        disk_id = self.create_disk(self.account_id, disk_type=disk_type)
        self.assertTrue(disk_id)

        self.lg("Make sure that disk status has changed to CREATED")
        disk = self.api.cloudapi.disks.get(disk_id)
        self.assertEqual(disk["status"], "CREATED")

        self.lg("List the %s disks, DS1 should be found." % disk_type)
        disks = self.api.cloudapi.disks.list(accountId=self.account_id, type=disk_type)
        self.assertTrue([True for d in disks if d["id"] == disk_id])

        if disk_type == "D":
            d_type = "B"
        else:
            d_type = "D"

        self.lg("List the %s disks, DS1 shouldn't be found." % d_type)
        disks = self.api.cloudapi.disks.list(accountId=self.account_id, type=d_type)
        self.assertFalse([True for d in disks if d["id"] == disk_id])

        self.lg("Delete non existing disk, should fail.")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.delete(diskId=disk_id + 9, detach=False)

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 404)

        self.lg("Delete DS1, should succeed.")
        response = self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)
        self.assertTrue(response)

        self.lg("Make sure that disk status has changed to TOBEDELETED")
        disk = self.api.cloudapi.disks.get(disk_id)
        self.assertEqual(disk["status"], "TOBEDELETED")

        self.lg("Delete disk DS1 permanently, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, permanently=True)

        self.lg("List the %s disks, DS1 shouldn't be there." % disk_type)
        disks = self.api.cloudapi.disks.list(accountId=self.account_id, type=disk_type)
        self.assertFalse([True for d in disks if d["id"] == disk_id])

        self.lg("%s ENDED" % self._testID)

    def test005_attaching_detaching_disks(self):
        """ OVC-023
        *Test case for attaching and detaching disks to a virtual machine*

        **Test Scenario:**

        #. Create a disk DS1, should succeed.
        #. Make sure disk is in CREATED state
        #. Create VM1
        #. Attach non existing disk to VM1, should fail
        #. Attach DS1 to VM1, should succeed
        #. Make sure disk is in ASSIGNED state
        #. Delete DS1 without detaching it, should fail
        #. Detach non existing disk, should fail
        #. Detach DS1, should succeed
        #. Make sure disk is in CREATED state
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create a disk DS1, should succeed.")
        disk_id = self.create_disk(self.account_id)
        self.assertTrue(disk_id)

        self.lg("Make sure that disk status has changed to CREATED")
        disk = self.api.cloudapi.disks.get(disk_id)
        self.assertEqual(disk["status"], "CREATED")

        self.lg("Create VM1")
        VM1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Attach non existing disk to VM1, should fail")
        with self.assertRaises(HTTPError) as e:
            response = self.api.cloudapi.machines.attachDisk(
                machineId=VM1_id, diskId=disk_id + 9
            )

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 404)

        self.lg("Attach DS1 to VM1, should succeed")
        response = self.api.cloudapi.machines.attachDisk(
            machineId=VM1_id, diskId=disk_id
        )
        self.assertTrue(response)
        self.lg("Make sure that disk status has changed to ASSIGNED")
        disk = self.api.cloudapi.disks.get(disk_id)
        self.assertEqual(disk["status"], "ASSIGNED")

        self.lg("Delete DS1 without detaching it, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)

        self.lg("- expected error raised %s" % e.exception.status_code)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("Detach DS1, should succeed")
        response = self.api.cloudapi.machines.detachDisk(
            machineId=VM1_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg("Make sure that disk status has changed to CREATED")
        disk = self.api.cloudapi.disks.get(disk_id)
        self.assertEqual(disk["status"], "CREATED")

        self.lg("%s ENDED" % self._testID)

    def test006_attach_disk_to_vm_of_another_account(self):
        """ OVC-030
        *Test case for attaching disk to a vm of another account*

        **Test Scenario:**

        #. Create account (AC1), should succeed.
        #. Create a disk (DS1) for account (AC1), should succeed.
        #. Create account (AC2), should succeed.
        #. Create cloud space (CS2) and virtual machine (VM2) for AC2, should succeed.
        #. Attach DS1 to VM2, should fail.
        #. Delete DS1.
        """

        self.lg("%s STARTED" % self._testID)

        self.lg("Create account (AC1), should succeed")
        ac1_name = str(uuid.uuid4())[0:8]
        ac1_id = self.cloudbroker_account_create(
            ac1_name, self.account_owner, self.email
        )

        self.lg("Create a disk (DS1) for account (AC1), should succeed")
        disk_id = self.create_disk(ac1_id)
        self.assertTrue(disk_id)

        self.lg("Create account (AC2), should succeed")
        self.lg(
            "Create cloud space (CS2) and virtual machine (VM2) for AC2, should succeed"
        )
        VM1_id = self.cloudapi_create_machine(cloudspace_id=self.cloudspace_id)

        self.lg("Attach DS1 to VM2, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.attachDisk(machineId=VM1_id, diskId=disk_id)
            self.assertEqual(e.exception.status_error, 409)

        self.lg("Delete DS1")
        response = self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)
        self.assertTrue(response)

        self.lg("%s ENDED" % self._testID)

    def test007_create_vm_with_unallowed_size(self):
        """ OVC-026
        *Test case for creating vm with unallowed size*

        **Test Scenario:**

        #. Create cloudspace CS1, should succeed.
        #. Create VM1 with unallowed size, should fail.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- Create cloudspace CS1, should succeed")
        allowed_sizes = [
            x["id"] for x in self.api.cloudapi.sizes.list(location=self.location)
        ]
        unallowed_size = random.choice(allowed_sizes)
        allowed_sizes.remove(unallowed_size)
        cloudspaceId = self.cloudapi_cloudspace_create(
            self.account_id,
            self.location,
            self.account_owner,
            allowedVMSizes=allowed_sizes,
        )

        self.lg("2- Create VM1 with unallowed size, should fail")
        with self.assertRaises(HTTPError) as e:
            self.cloudapi_create_machine(
                cloudspace_id=cloudspaceId, size_id=unallowed_size
            )

        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    def test008_disk_resize(self):
        """ OVC-041
        *Test case for disk resizing*

        **Test Scenario:**

        #. Create a Disk (DS1) with size (S1).
        #. Resize DS1 to a size less than S1, should fail.
        #. Resize DS1 to a size greater than S1, should succeed.
        #. Resize DS1 to a very large size, should fail.
        #. Delete DS1.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create a Disk (DS1) with size (S1)")
        s1 = random.randint(10, 50)
        disk_id = self.create_disk(self.account_id, size=s1)
        self.assertTrue(disk_id)

        self.lg("Resize DS1 to a size less than S1, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.resize(diskId=disk_id, size=s1 - 1)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("Resize DS1 to a size greater than S1, should succeed")
        self.api.cloudapi.disks.resize(diskId=disk_id, size=s1 + 1)
        new_size = self.api.cloudapi.disks.get(diskId=disk_id)["sizeMax"]
        self.assertEqual(new_size, s1 + 1)

        self.lg("Resize DS1 to a very large size, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.resize(diskId=disk_id, size=90000000000)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("Delete DS1")
        response = self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)
        self.assertTrue(response)

        self.lg("%s ENDED" % self._testID)
