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
            external_network_id = self.create_external_network(
                name="test-external-network", vlan=None
            )
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

    def test006_routeros_check(self):
        """ OVC-069
        *Test case for RouterOS selfhealing script*

        **Test Scenario:**

        #. Create and deploy a cloudspace.
        #. Go to the node on which the ROS is created and shuts down its domain, should succeed.
        #. Run ROS selfhealing script, should succeed.
        #. Ensure the ROS is running, should succeed.
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("Create and deploy a cloudspace")

        def ros_status(name, nid):
            ros_list = self.execute_command_on_physical_node(
                "virsh list --all", nid
            ).split("\n")
            ros = [ros for ros in ros_list if ros.find(name) != -1][0]
            for status in ["running", "shut off"]:
                if ros.find(status) != -1:
                    return {"status": status}

        nid = self.get_physical_node_id(self.cloudspace_id)
        network_id = self.get_cloudspace_network_id(self.cloudspace_id)
        ros_name = "routeros_%04x" % network_id

        # check if ROS is running
        self.assertEqual(ros_status(ros_name, nid)["status"], "running")

        self.lg(
            "Go to the node on which the ROS is created and shuts down its domain, should succeed."
        )
        cmd = "virsh shutdown {}".format(ros_name)
        self.execute_command_on_physical_node(cmd, nid)

        # wait for domain to shut down
        self.wait_for_status(
            status="shut off", func=ros_status, timeout=60, name=ros_name, nid=nid
        )

        self.lg("Run ROS selfhealing script, should succeed.")
        acl = j.clients.agentcontroller.get()
        output = acl.executeJumpscript("greenitglobe", "routeros_check", nid=nid)
        self.assertEqual(output["state"], "OK")

        self.lg("Ensure the ROS is running, should succeed.")
        # wait for ROS to start running
        self.wait_for_status(
            status="running", func=ros_status, timeout=60, name=ros_name, nid=nid
        )

        self.lg("%s ENDED" % self._testID)

