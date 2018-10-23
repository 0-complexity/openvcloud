import unittest
from ....utils.utils import BasicACLTest
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from JumpScale import j

class DecommissionTests(BasicACLTest):
    def setUp(self):
        super(DecommissionTests, self).setUp()

    def test01_decommission_node(self):
        """ OVC-048
        *Test case for checking cloned VM ip, portforwards and credentials*

        **Test Scenario:**

        #. Create new cloudspace (CS1).
        #. Create virtual machine (VM1).
        #. Decommission node (N1), should succeed.
        #. Check that cloudspace (CS1)'s vritual firewall is moved to another node and running.
        #. Check that virtual machine (VM1) is moved to another node and running.
        """
        self.lg("%s STARTED" % self._testID)

        scl = j.clients.osis.getNamespace('system')
        ccl = j.clients.osis.getNamespace('cloudbroker')

        self.lg("Create new cloudspace (CS1)")
        cloudspaceId = self.cloudapi_cloudspace_create()

        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        nid = vfw["nid"]
        stack = ccl.stack.searchOne({"referenceId":str(nid)})

        self.lg("Create virtual machine (VM1)")
        machineId = self.api.cloudapi_create_machine(cloudspaceId=cloudspaceId, stackId=stack["id"])

        self.lg("Decommission node (N1), should succeed")
        self.api.cloudbroker.node.decommission(nid=nid)
        self.wait_for_status(
            "DECOMMISSIONED", scl.node.searchOne({"id":nid}), nid=nid
        )

        self.lg("Check that cloudspace (CS1)'s vritual firewall is moved to another node and running")
        vfw = self.api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)
        self.assertNotEqual("nid", nid)
        self.assertEqual("RUNNING", vfw["status"])

        self.lg("Check that virtual machine (VM1) is moved to another node and running")
        machine = self.api.cloudbroker.machine.get(machineId=machineId)
        self.assertNotEqual("stackId", stack["id"])
        self.assertEqual("RUNNING", machine["status"])

        self.lg("%s ENDED" % self._testID)
