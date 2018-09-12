# coding=utf-8
import time
import random
import unittest

from JumpScale import j
from ....utils.utils import BasicACLTest
from nose_parameterized import parameterized


class NetworkBasicTests(BasicACLTest):
    def setUp(self):
        super(NetworkBasicTests, self).setUp()
        self.acl_setup()

    def test001_release_networkId(self):
        """ OVC-010
        * Test case for check that deleting Account with multiple Cloud Spaces will release all Cloud Spaces network IDs*

        **Test Scenario:**

        #. create three cloudspaces with user1 and get its network ID
        #. Delete the first cloudspace
        #. Check the release network ID after destroying the first cloudspace
        #. Delete the account
        #. Check the release network ID are in the free network IDs list
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- create three cloudspaces with user1 and get its network ID")
        cloud_space_networkId = []
        ccl = j.clients.osis.getNamespace("cloudbroker")

        for csNumbers in range(0, 3):
            self.cloudspaceId = self.cloudapi_cloudspace_create(
                account_id=self.account_id,
                location=self.location,
                access=self.account_owner,
                api=self.account_owner_api,
            )
            cloud_space_networkId.append(
                ccl.cloudspace.get(self.cloudspaceId).networkId
            )

        self.lg("2- Delete the third cloudspace")
        self.account_owner_api.cloudapi.cloudspaces.delete(
            cloudspaceId=self.cloudspaceId, permanently=True
        )

        self.lg("3- Check the release network ID after destroying the third cloudspace")
        for timeDelay in range(0, 10):
            if ccl.cloudspace.get(self.cloudspaceId).networkId:
                time.sleep(1)
            else:
                break
        self.assertFalse(ccl.cloudspace.get(self.cloudspaceId).networkId)

        self.lg("4- delete account: %s" % self.account_id)
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, permanently=True, reason="testing"
        )

        self.lg("5- Check the release network ID are in the free network IDs list")
        lcl = j.clients.osis.getNamespace("libvirt")
        for csNumbers in range(0, 3):
            for timeDelay in range(0, 10):
                released_network_Id = lcl.networkids.get(
                    j.application.whoAmI.gid
                ).networkids
                if cloud_space_networkId[csNumbers] not in released_network_Id:
                    time.sleep(1)
                else:
                    break
            self.assertTrue(cloud_space_networkId[csNumbers] in released_network_Id)
        self.lg("%s ENDED" % self._testID)

    def has_cloudspacebridges(self, cloudspaceId=None, nid=None, network_id=None):
        cloudspaceId = cloudspaceId or self.cloudspace_id
        nid = nid or self.get_physical_node_id(cloudspaceId)
        network_id = network_id or self.get_cloudspace_network_id(cloudspaceId)
        hexNetworkID = "%04x" % network_id
        command = "ls /sys/class/net"  # All created bridges in this node
        result = self.execute_command_on_physical_node(command, nid)
        return "space_" + hexNetworkID in result

    def test002_clean_ovs_bridge(self):
        """ OVC-011
         * Test case verify the cleaning OVS bridges when deleting a cloudspace operation

        **Test Scenario:**

        #. Create a new cloudspace and deploy it
        #. Get the cloudspace Network ID and convert it to hex
        #. Make sure that the bridge is created
        #. Delete this cloudspace
        #. make sure that the bridge is released
        """
        self.lg("%s STARTED" % self._testID)
        self.api.cloudbroker.cloudspace.deployVFW(self.cloudspace_id)
        self.lg("Make sure that the bridge is created")
        self.assertTrue(self.has_cloudspacebridges())

        self.lg("Stop ros check if bridge is gone")
        self.api.cloudbroker.cloudspace.stopVFW(self.cloudspace_id)
        self.assertFalse(self.has_cloudspacebridges())

        self.lg("Start VFW again")
        self.api.cloudbroker.cloudspace.startVFW(self.cloudspace_id)
        self.lg("Make sure that the bridge is created")
        self.assertTrue(self.has_cloudspacebridges())
        cloudspace = self.api.models.cloudspace.get(self.cloudspace_id)
        network_id = cloudspace.networkId
        vcl = j.clients.osis.getNamespace("vfw")
        nid = vcl.virtualfirewall.get("{}_{}".format(cloudspace.gid, network_id)).nid

        self.lg("Delete this cloudspace")
        self.account_owner_api.cloudapi.cloudspaces.delete(
            cloudspaceId=self.cloudspace_id, permanently=True
        )

        self.lg("Make sure that the bridge is deleted")
        self.assertFalse(self.has_cloudspacebridges(nid=nid, network_id=network_id))

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["Ubuntu 16.04 x64", "Windows 2012r2 Standard"])
    def test003_port_forwarding_creation(self, image_name):
        """OVC- 007
        * Test case verify the adding port forward to a machine

        #. Create a cloudspace and get its public ip
        #. Create a virtual machine
        #. Check that the cloudspace has a public IP
        #. Create a ssh / 22 port forwarding
        #. Check the port forwarding list is updated
        #. Check connection to the VM over this port
        #. Create a ftp / 21 port forwarding
        #. Check the port forwarding list is updated
        #. Check connection to the VM over this port
        #. Create a HTTP / 80 port forwarding
        #. Check the port forwarding list is updated
        #. Check connection to the VM over this port
        #. Create HTTPS / 443 port forwarding
        #. Check the port forwarding list is updated
        #. Check connection to the VM over this port
        #. port forwarding RDP / 3389 port forwarding
        #. Check the port forwarding list is updated
        #. Check connection to the VM over this port
        """

        self.lg("%s STARTED" % self._testID)

        self.wait_for_status(
            "DEPLOYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("Check the cloudspace has a public ip")
        cloudspace_puplicIp = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)[
            "publicipaddress"
        ]
        self.assertNotEqual(cloudspace_puplicIp, "")

        self.lg("Create a virtual machine with image [{}]".format(image_name))
        imageId = [
            image["id"]
            for image in self.api.cloudapi.images.list()
            if image["name"] == image_name
        ]
        self.assertTrue(imageId, "Image [{}] doesn't exist in images list")
        machineId = self.cloudapi_create_machine(
            self.cloudspace_id, image_id=imageId[0], disksize=50
        )

        self.lg("- Make sure that the machine got an IP")
        for i in range(300):
            machineIp = self.api.cloudapi.machines.get(machineId)["interfaces"][0][
                "ipAddress"
            ]
            if machineIp != "Undefined":
                break
            else:
                time.sleep(1)
        else:
            self.fail("machine didn't get an ip address")

        self.lg("Create a port forwarding which is covering all combinations")
        localPorts = [21, 22, 80, 443, 21, 3389]
        publicPort = random.randint(4000, 5000)
        protocolItems = ["tcp", "udp"]
        lastAddedIndex = 0

        for protocol in protocolItems:
            for localPort in localPorts:
                self.lg(
                    "Create portforward for port %s to public port %s "
                    % (localPort, publicPort)
                )
                self.api.cloudapi.portforwarding.create(
                    cloudspaceId=self.cloudspace_id,
                    publicIp=cloudspace_puplicIp,
                    publicPort=publicPort,
                    machineId=machineId,
                    localPort=localPort,
                    protocol=protocol,
                )

                portforwarding_info = self.api.cloudapi.portforwarding.list(
                    cloudspaceId=self.cloudspace_id, machineId=machineId
                )

                self.assertEqual(
                    portforwarding_info[lastAddedIndex]["localPort"], str(localPort)
                )
                self.assertEqual(
                    portforwarding_info[lastAddedIndex]["publicPort"], str(publicPort)
                )
                self.assertEqual(
                    portforwarding_info[lastAddedIndex]["protocol"], str(protocol)
                )

                publicPort += 1
                lastAddedIndex += 1

                self.lg("test ssh connection")
                if localPort == 22:
                    self.lg("Get the virtual machine user name and password")
                    username = self.api.cloudapi.machines.get(machineId)["accounts"][0][
                        "login"
                    ]
                    password = self.api.cloudapi.machines.get(machineId)["accounts"][0][
                        "password"
                    ]
                    command = (
                        "sshpass -p "
                        + password
                        + " ssh -p "
                        + str(publicPort)
                        + " "
                        + username
                        + "@"
                        + cloudspace_puplicIp
                        + "; uname -a; "
                    )
                    acl = j.clients.agentcontroller.get()
                    output = acl.executeJumpscript(
                        "jumpscale", "exec", nid=3, args={"cmd": command}
                    )
                    if output["state"] == "OK":
                        if "Linux" not in output["result"][1]:
                            raise NameError("This command:" + command + "is wrong")

        self.api.cloudapi.machines.stop(machineId=machineId)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machineId)["status"], "HALTED"
        )
        self.lg("%s ENDED" % self._testID)

    def test004_move_virtual_firewall(self):
        """ OVC-014
        * Test case for moving virtual firewall form one node to another

        **Test Scenario:**

        #. create account and cloudspace
        #. deploy the created cloudspace
        #. get nodeId of the cloudspace virtual firewall
        #. get another nodeId to move the virtual firewall to
        #. move virtual firewall to another node, should succeed

        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- deploy the created cloudspace")
        self.api.cloudbroker.cloudspace.deployVFW(self.cloudspace_id)
        self.wait_for_status(
            "DEPLOYED",
            self.account_owner_api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("2- get nodeId of the cloudspace virtual firewall")
        nodeId = self.get_physical_node_id(self.cloudspace_id)
        self.assertTrue(self.has_cloudspacebridges())

        self.lg("3- get another nodeId to move the virtual firewall to")
        other_nodeId = self.get_nodeId_to_move_VFW_to(nodeId)

        if not other_nodeId:
            self.skipTest("No active node to move the VFW to")

        self.lg("4- move virtual firewall to another node")
        self.api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
            cloudspaceId=self.cloudspace_id, targetNid=other_nodeId
        )
        new_nodeId = self.get_physical_node_id(self.cloudspace_id)
        self.assertEqual(other_nodeId, new_nodeId)
        self.assertFalse(self.has_cloudspacebridges(nid=nodeId))

        self.wait_for_status(
            "DEPLOYED",
            self.account_owner_api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )
        self.lg("%s ENDED" % self._testID)

    def test005_external_network_with_empty_vlan(self):
        """ OVC-051
        * Test case for creating external network with empty vlan tag

        **Test Scenario:**

        #. Create external network (EN1) with empty vlan tag, should succeed.
        #. Get external network (EN1)'s info using osis client.
        #. Check that external network (EN1)'s vlan tag equal to 0, should succeed.
        #. Remove external network (EN1), should succeed.
        """

        self.lg("Create external network (EN1) with empty vlan tag, should succeed")
        try:
            external_network_id = self.create_external_network(name="test-external-network", vlan=None)
            self.lg("Get external network (EN1)'s info using osis client")
            osis_client = j.clients.osis.getNamespace("cloudbroker")
            external_network_info = osis_client.externalnetwork.get(external_network_id)
            self.lg(
                "Check that external network (EN1)'s vlan tag equal to 0, should succeed"
            )
            self.assertEqual(external_network_info.vlan, 0)
        except:
            raise
        finally:
            self.lg("Remove  external network (EN1), should succeed")
            self.api.cloudbroker.iaas.deleteExternalNetwork(external_network_id)
