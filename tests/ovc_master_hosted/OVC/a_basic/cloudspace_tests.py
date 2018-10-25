# coding=utf-8
import unittest, time, random, socket
from ....utils.utils import BasicACLTest, VMClient
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from JumpScale import j


class CloudspaceBasicTests(BasicACLTest):
    def setUp(self):
        super(CloudspaceBasicTests, self).setUp()
        self.default_setup(False)

    @parameterized.expand(["routeros", "vgw"])
    def test001_get_list_update_delete_cloudspace(self, cs_type):
        """ OVC-01
        *Test case for test create/get/list/update/delete cloudspace.*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Get cloudspace (CS1) info, should succeed.
        #. List cloudspaces, cloudspace (CS1) should be listed.
        #. Update cloudspace (CS1)'s name, should succeed.
        #. Delete cloudspace (CS1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Get cloudspace (CS1) info, should succeed")
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspaceId)
        self.assertEqual(cloudspace["type"], cs_type)

        self.lg("List cloudspaces, cloudspace (CS1) should be listed")
        cloudspaces = self.api.cloudapi.cloudspaces.list()
        self.assertIn(cloudspaceId, [cs["id"] for cs in cloudspaces])

        self.lg("Update cloudspace (CS1)'s name, should succeed")
        name = "cloudspace-{}".format(cloudspaceId)
        self.api.cloudapi.cloudspaces.update(cloudspaceId=cloudspaceId, name=name)
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspaceId)
        self.assertEqual(cloudspace["name"], name)

        self.lg("Delete cloudspace (CS1), should succeed")
        self.api.cloudapi.cloudspaces.delete(cloudspaceId=cloudspaceId, permanently=True)
        cloudspaces = self.api.cloudapi.cloudspaces.list()
        self.assertNotIn(cloudspaceId, [cs["id"] for cs in cloudspaces])

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["routeros", "vgw"])
    def test002_get_stop_start_vfw(self, cs_type):
        """ OVC-02
        *Test case for test get/stop/start virtual firewall.*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Get cloudspace (CS1)'s vfw info, should succeed.
        #. Stop cloudspace (CS1)'s vfw, should succeed.
        #. Start cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        self.lg("Get cloudspace (CS1)'s vfw info, should succeed")
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertEqual(vfw["domain"], str(cloudspaceId))
        self.assertEqual(vfw["status"], "RUNNING")

        self.lg("Stop cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.stopVFW(cloudspaceId=cloudspaceId)
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertEqual(vfw["status"], "HALTED")

        self.lg("Start cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.startVFW(cloudspaceId=cloudspaceId)
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertEqual(vfw["status"], "RUNNING")

        self.lg("Try to connect to vm (VM1), should succeed")
        self.assertTrue(self.check_vm(machineId))

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["routeros", "vgw"])
    def test003_destoy_deploy_vfw(self, cs_type):
        """ OVC-03
        *Test case for test get/stop/start/destroy/deploy virtual firewall.*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Destroy cloudspace (CS1)'s vfw, should succeed.
        #. Deploy cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspaceId)

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        self.lg("Destroy cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.destroyVFW(cloudspaceId=cloudspaceId)
        self.wait_for_status(
            "VIRTUAL", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
        )

        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("Deploy cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.deployVFW(
            cloudspaceId=cloudspaceId, type=cs_type
        )
        self.wait_for_status(
            "DEPLOYED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
        )

        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertEqual(vfw["status"], "RUNNING")

        self.lg("Try to connect to vm (VM1), should succeed")
        self.assertTrue(self.check_vm(machineId))

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["routeros", "vgw"])
    def test004_move_vfw(self, cs_type):
        """ OVC-04
        *Test case for test move virtual firewall.*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Stop cloudspace (CS1)'s vfw, should succeed.
        #. Move cloudspace (CS1)'s vfw to another node, should succeed.
        #. Start cloudspace (CS1)'s vfw, should succeed.
        #. Try to connect to vm (VM1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        self.lg("Stop cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.stopVFW(cloudspaceId=cloudspaceId)
        self.wait_for_status(
            "HALTED", self.api.cloudbroker.cloudspace.getVFW, cloudspaceId=cloudspaceId
        )

        self.lg("Move cloudspace (CS1)'s vfw to another node, should succeed")
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        nodeId = self.get_running_nodeId(except_nodeid=vfw["nid"])
        if not nodeId:
            self.skipTest("No enabled nodes were found to move the VFW")

        self.api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
            cloudspaceId, nodeId
        )
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId)
        self.assertEqual(vfw["nid"], nodeId)

        self.lg("Start cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.startVFW(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudbroker.cloudspace.getVFW, cloudspaceId=cloudspaceId
        )

        self.lg("Try to connect to vm (VM1), should succeed")
        self.assertTrue(self.check_vm(machineId))

        self.lg("%s ENDED" % self._testID)

    def test005_reset_vfw(self):
        """ OVC-05
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
        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type="routeros")

        self.lg("Create virtual machine (VM1)")
        machine_id = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_id
        )

        self.lg(
            "Execute script on routeros of cloudspace (CS1) to create portforward (PF1), should succeed"
        )
        cloudspace_ip = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspaceId)[
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
            cloudspaceId, script=script
        )
        self.lg("Try to connect to virtual machine (VM1) through PF1, should succeed")
        self.assertTrue(self.check_vm(machine_id, port=public_port))

        self.lg("Reset cloudspace (CS1)'s vfw, should succeed")
        self.api.cloudbroker.cloudspace.resetVFW(
            cloudspaceId=cloudspaceId, resettype="factory"
        )
        self.lg(
            "Try to connect to virtual machine (VM1) through portforward (PF1), should fail"
        )
        
        self.assertFalse(self.check_vm(machine_id, port=public_port, timeout=5))

        self.lg("Destroy cloudspace (CS1)'s vfw")
        self.api.cloudbroker.cloudspace.destroyVFW(cloudspaceId=cloudspaceId)
        
        self.lg("Try to reset cloudspace (CS1)'s vfw, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.cloudspace.resetVFW(
                cloudspaceId, resettype="factory"
            )
        self.assertEqual(e.exception.status_code, 400)

    @parameterized.expand(["routeros", "vgw"])
    def test006_change_cs_type(self, cs_type):
        """ OVC-06
        *Test case for test change virtual firewall's type*

        **Test Scenario:**
        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Change cloudspace (CS1)'s vfw type to vgw, should succeed.
        #. Change cloudspace (CS1)'s vfw type to routeros, should fail.
        #. Try to connect to vm (VM1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        if cs_type == "routeros":
            self.lg("Change cloudspace (CS1)'s vfw type, should succeed")
            self.api.cloudbroker.cloudspace.changeRouterType(
                cloudspaceId=cloudspaceId, routertype="vgw"
            )
            vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
            self.assertEqual(vfw["type"], "vgw")

            self.lg("Try to connect to vm (VM1), should succeed")
            self.assertTrue(self.check_vm(machineId))

        else:
            with self.assertRaises(ApiError):
                self.api.cloudbroker.cloudspace.changeRouterType(
                    cloudspaceId=cloudspaceId, routertype="routeros"
                )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["routeros", "vgw"])
    def test007_disable_enable_cloudspace(self, cs_type):
        """ OVC-07
        *Test case for test disable/enable cloudspace.*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Disable cloudspace (CS1), should succeed.
        #. Check cloudspace (CS1)'s private network, should be halted.
        #. Check virtual machine (VM1) status, should be halted.
        #. Create user (US1) without Admin access.
        #. Authenticate (US1), should succeed.
        #. Add user (US1) to cloudsapce (CS1), should succeed.
        #. Try to start virtual machine (VM1) using user (US1), should fail.
        #. Enable cloudspace (CS1), should succeed.
        #. Check that cloudspace (CS1)'s private network is running.
        #. Try to start virtual machine (VM1) using user (US1), should succeed.
        #. Disable cloudspace (CS1) again, should succeed.
        #. Delete virtual machine (VM1), should succeed.
        #. Delete cloudspace (CS1), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create virtual machine (VM1)")
        machineId = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machineId
        )

        self.lg("Disable cloudspace (CS1), should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.disable(
                cloudspaceId=cloudspaceId, reason="test"
            )
        )
        self.wait_for_status(
            "DISABLED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
        )

        self.lg("Check cloudspace (CS1)'s private network, should be halted")
        self.wait_for_status(
            "HALTED", self.api.cloudbroker.cloudspace.getVFW, cloudspaceId=cloudspaceId
        )

        self.lg("Check virtual machine (VM1) status, should be halted")
        machine_info = self.api.cloudapi.machines.get(machineId=machineId)
        self.assertEqual(machine_info["status"], "HALTED")

        self.lg("Create user (US1) without Admin access")
        user = self.cloudbroker_user_create()

        self.lg("Authenticate (US1), should succeed")
        user_api = self.get_authenticated_user_api(user)

        self.lg("Add user (US1) to cloudsapce (CS1), should succeed")
        self.add_user_to_cloudspace(cloudspaceId, user, "ACDRUX")

        self.lg("Try to start virtual machine (VM1), should fail")
        with self.assertRaises(ApiError):
            user_api.cloudapi.machines.start(machineId=machineId)

        self.lg("Enable cloudspace (CS1), should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.enable(
                cloudspaceId=cloudspaceId, reason="test"
            )
        )
        self.wait_for_status(
            "DEPLOYED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId
        )

        self.lg("Check that cloudspace (CS1)'s private network is running")
        self.wait_for_status(
            "RUNNING", self.api.cloudbroker.cloudspace.getVFW, cloudspaceId=cloudspaceId
        )

        self.lg("Try to start virtual machine (VM1) using user (US1), should succeed")
        self.assertTrue(self.api.cloudapi.machines.start(machineId=machineId))

        self.lg("Disable cloudspace (CS1) again, should succeed")
        self.assertTrue(
            self.api.cloudapi.cloudspaces.disable(
                cloudspaceId=cloudspaceId, reason="test"
            )
        )

        self.lg("Delete machine (VM1), should succeed")
        self.api.cloudapi.machines.delete(machineId=machineId, permanently=True)

        self.lg("Delete cloudspace (CS1), should succeed")
        self.api.cloudapi.cloudspaces.delete(
            cloudspaceId=cloudspaceId, permanently=True
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["routeros", "vgw"])
    def test008_create_portforward(self, cs_type):
        """ OVC-08
        *Test case for test portforward*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Create virtual machine (VM2).
        #. Create portforward for virtual machine (VM1).
        #. Create portforward for virtual machine (VM2) using same public port, should fail.
        #. Create portforward for virtual machine (VM2), should succeed.
        #. Try to connect to vm (VM1), should succeed.
        #. Try to connect to vm (VM2), should succeed.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create(type=cs_type)
        cloudspace = self.api.cloudapi.cloudspaces.get(cloudspaceId=cloudspaceId)
        puplicIp = cloudspace["publicipaddress"]

        self.lg("Create virtual machine (VM1)")
        machine_1_Id = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_1_Id
        )

        self.lg("Create virtual machine (VM2)")
        machine_2_Id = self.cloudapi_create_machine(cloudspaceId)
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=machine_2_Id
        )

        vm1_pf_info = {
            "cloudspaceId": cloudspaceId,
            "machineId": machine_1_Id,
            "publicIp": puplicIp,
            "publicPort": 2201,
            "localPort": 22,
            "protocol": "tcp"
        }

        self.lg("Create portforward for virtual machine (VM1)")
        self.api.cloudapi.portforwarding.create(** vm1_pf_info)

        portforwarding_info = self.api.cloudapi.portforwarding.list(
            cloudspaceId=cloudspaceId, machineId=machine_1_Id
        )
        self.assertDictEqual(portforwarding_info, vm1_pf_info)

        self.lg("Create portforward for virtual machine (VM2) using same public port, should fail")
        vm2_pf_info = vm1_pf_info.copy()
        vm2_pf_info["machineId"] = machine_2_Id
        with self.assertRaises(ApiError) as e:
            self.api.cloudapi.portforwarding.create(** vm2_pf_info)

        self.lg("Create portforward for virtual machine (VM2), should succeed")
        vm2_pf_info["publicPort"] = 2202
        self.api.cloudapi.portforwarding.create(** vm2_pf_info)

        portforwarding_info = self.api.cloudapi.portforwarding.list(
            cloudspaceId=cloudspaceId, machineId=machine_1_Id
        )
        self.assertDictEqual(portforwarding_info, vm2_pf_info)

        self.lg("Try to connect to vm (VM1), should succeed")
        self.assertTrue(self.check_vm(machine_1_Id, port=2201))

        self.lg("Try to connect to vm (VM2), should succeed")
        self.assertTrue(self.check_vm(machine_2_Id, port=2202))

    @parameterized.expand(["routeros", "vgw"])
    def test001_check_machines_networking(self, cs_type):
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
        cs_type_2 = "routeros" if cs_type == "vgw" else "vgw"
        
        self.lg("Create new cloudspace (CS1) with type {}".format(cs_type))
        cloudspace_1_id = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create new cloudspace (CS2) with type {}".format(cs_type))
        cloudspace_2_id = self.cloudapi_cloudspace_create(type=cs_type)

        self.lg("Create new cloudspace (CS3) with type {}".format(cs_type_2))
        cloudspace_3_id = self.cloudapi_cloudspace_create(type=cs_type_2)

        self.lg("Create virtual machine (VM1) in cloudspace (CS1)")
        machine_1_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_1_id)
        machine_1_ipaddress = self.get_machine_ipaddress(machine_1_id)
        self.assertTrue(machine_1_ipaddress)
        machine_1_client = VMClient(machine_1_id)

        self.lg("Create virtual machine (VM2) in cloudspace (CS2)")
        machine_2_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_2_id)
        machine_2_ipaddress = self.get_machine_ipaddress(machine_2_id)
        self.assertTrue(machine_2_ipaddress)
        machine_2_client = VMClient(machine_2_id)

        self.lg("Create virtual machine (VM3) in cloudspace (CS3)")
        machine_3_id = self.cloudapi_create_machine(cloudspace_id=cloudspace_3_id)
        machine_3_ipaddress = self.get_machine_ipaddress(machine_3_id)
        self.assertTrue(machine_3_ipaddress)
        machine_3_client = VMClient(machine_3_id)

        self.lg("From virtual machine (VM1) ping google, should succeed")
        _, stdout, _ = machine_1_client.execute("ping -c3 8.8.8.8")
        self.assertIn("3 received", stdout.read())

        self.lg("From virtual machine (VM3) ping google, should succeed")
        _, stdout, _ = machine_3_client.execute("ping -c3 8.8.8.8")
        self.assertIn("3 received", stdout.read())

        self.lg("From virtual machine (VM2) ping virtual machine (VM1), should succeed")
        _, stdout, _ = machine_2_client.execute("ping -c3 {}".format(machine_1_ipaddress))
        self.assertIn("3 received", stdout.read())

        self.lg("From virtual machine (VM2) ping virtual machine (VM3), should fail")
        _, stdout, _ = machine_2_client.execute("ping -c3 {}".format(machine_3_ipaddress))
        self.assertIn(", 100% packet loss", stdout.read())

        
