# coding=utf-8
import unittest, socket, random
from ....utils.utils import BasicACLTest
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from JumpScale import j
from nose_parameterized import parameterized


class CloudspaceTests(BasicACLTest):
    def setUp(self):
        super(CloudspaceTests, self).setUp()
        self.default_setup(False)

    @parameterized.expand(["routeros", "vgw"])
    def test001_validate_deleted_cloudspace_with_running_machines(self, cs_type):
        """ OVC-020
        *Test case for validate deleted cloudspace with running machines get destroyed.*

        **Test Scenario:**
        #. Create new cloudspace CS1
        #. Create 3+ vm's possible with different images on new cloudspace, should succeed
        #. Cloudspace status should be DEPLOYED, should succeed
        #. Try to delete the cloudspace with delete, should fail with 409 conflict
        #. Delete the cloudspace with destroy, should succeed
        #. Try list user's cloud spaces, should return empty list, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace CS1")
        cloudspace_id = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg(
            "1- Create 3+ vm's possible with different images on new cloudspace, "
            "should succeed"
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
    @parameterized.expand(["routeros", "vgw"])
    def test002_add_remove_AllowedSize_to_cloudspace(self, cs_type):
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
        self.lg("Create new cloudspace CS1")
        cloudspace_id = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("1- Get list of available sizes in location, should succeed.")
        location_sizes = self.api.cloudapi.sizes.list(location=self.location)
        selected_size = random.choice(location_sizes)

        self.lg("2- Add random size to CS1, should succeed")
        response = self.api.cloudapi.cloudspaces.addAllowedSize(
            cloudspaceId=cloudspace_id, sizeId=selected_size["id"]
        )
        self.assertTrue(response)

        self.lg("3- Check if the size has been added successfully to CS1")
        cloudspace_sizes = self.api.cloudapi.sizes.list(
            location=self.location, cloudspaceId=cloudspace_id
        )
        self.assertIn(selected_size, cloudspace_sizes)

        self.lg("4- Remove this size from CS1, should succeed")
        response = self.api.cloudapi.cloudspaces.removeAllowedSize(
            cloudspaceId=cloudspace_id, sizeId=selected_size["id"]
        )
        self.assertTrue(response)

        self.lg("5- check if the size has been removed successfully from CS1")
        cloudspace_sizes = self.api.cloudapi.sizes.list(
            location=self.location, cloudspaceId=cloudspace_id
        )
        self.assertNotIn(selected_size, cloudspace_sizes)

        self.lg("6- Remove this size again, should fail")
        with self.assertRaises(ApiError):
            self.api.cloudapi.cloudspaces.removeAllowedSize(
                cloudspaceId=cloudspace_id, sizeId=selected_size["id"]
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

        self.lg("Create new cloudspace (CS1)")
        cloudspace_id = self.cloudapi_cloudspace_create(type="routeros")
        
        self.lg("Create virtual machine (VM1)")
        vm_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_id)

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
            cloudspace_id, script=script
        )

        self.lg("Connect to VM1 through PF1 , should succeed")
        self.assertTrue(self.check_vm(vm_id, port=pb_port))

        self.lg("%s ENDED" % self._testID)

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
        cloudspace_id = self.cloudapi_cloudspace_create(type="routeros")

        self.lg(
            "Check that the new cloudspace is created on the cpu node with smallest number of router os"
        )
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspace_id)
        self.assertIn(vfw["nid"], available_stacks)
