import uuid
import time
import unittest
from random import randint
from ....utils.utils import BasicACLTest
from JumpScale.portal.portal.PortalClient2 import ApiError


class ACLACCOUNT(BasicACLTest):
    def setUp(self):
        super(ACLACCOUNT, self).setUp()
        self.acl_setup(False)


class level1_group(ACLACCOUNT):
    def test001_level1_and_accounts(self):
        """ ACL-61
        *Test case for  user with level1+admin groups dealing with accounts .*

        **Test Scenario:**

        #. create use1 and user2  with level1+admin groups
        #. create account with user1
        #. disable created account by user2 should return succeed
        #. update  created account name by user2 should succeed
        #. get list of accounts for user2 should be empty
        #. enable created account by user2 should return succeed
        #. add user2 to crated account should return succeed
        #. delete user1 from created account should return succeed
        #. delete created account by user 1 should return succeed
        """
        self.lg("%s STARTED" % self._testID)
        self.user_group = ["admin", "level1"]
        self.lg("create user1 and user2  with level1 + admin group")
        self.user1 = self.cloudbroker_user_create(group=self.user_group)
        self.user2 = self.cloudbroker_user_create(group=self.user_group)

        self.lg("1- create user1 %s with level1 and admin  domain " % self.user1)
        self.lg("- create user2 %s with level1 and admin  domain " % self.user2)

        self.user1_api = self.get_authenticated_user_api(self.user1)
        self.user2_api = self.get_authenticated_user_api(self.user2)

        self.lg(" 2- create account with user 1  ")

        accountId = self.user1_api.cloudbroker.account.create(
            name=self.user1,
            username=self.user1,
            email="%s@gmail.com" % self.user1,
            maxMemoryCapacity=-1,
            maxVDiskCapacity=-1,
            maxCPUCapacity=-1,
            maxNumPublicIP=-1,
        )
        self.assertTrue(accountId)

        self.lg(" 3- disable account 1 by user 2  ")

        response = self.user2_api.cloudbroker.account.disable(
            accountId=accountId, reason=" test"
        )
        self.assertTrue(response)
        self.lg(" 4- update account 1 by user 2  ")

        response = self.user2_api.cloudbroker.account.update(
            accountId=accountId, name=self.user2
        )
        self.assertTrue(response)
        details = self.user2_api.cloudapi.accounts.get(accountId=accountId)
        self.assertEqual(details["name"], self.user2)

        self.lg(" 5- enable account 1 by user 2  ")

        response = self.user2_api.cloudbroker.account.enable(
            accountId=accountId, reason="test"
        )
        self.assertTrue(response)

        self.lg("6- get list of account of user2 ")
        account_list = self.user2_api.cloudapi.accounts.list()
        self.assertEqual(account_list, [])
        self.lg("7- add user 2 to account ")

        response = self.user2_api.cloudbroker.account.addUser(
            accountId=accountId, username=self.user2, accesstype="ARCXDU"
        )
        self.lg("%s" % response)
        self.assertTrue(response)

        self.lg(" 8- delete user1 from created account ")

        response = self.user2_api.cloudbroker.account.deleteUser(
            accountId=accountId, username=self.user1, recursivedelete="true"
        )
        self.assertTrue(response)

        self.lg("9-delete created account by user1 ")

        self.user1_api.cloudbroker.account.delete(
            accountId=accountId, reason="test", permanently=True
        )

    def test002_level1_and_cloudspaces(self):
        """ ACL-62
        *test case for user with level1+admin groups dealing with cloudspaces.*

        **Test Scenario:**

        #. create use1 and user2  with level1+admin group
        #. create 3 cloudspaces by user2 should be succeed
        #. rename cloudspace1 by user1 should return succeed
        #. add extraIP for cloudspace1  by user1 should return succeed
        #. deployVFW for created cloudspace1  by user1 should return succeed
        #. destroy VFW by user1 should be succeed
        #. reset VFW by user1 should be succeed
        #. start VFW by user1 should be succeed
        #. stop VFW by user1 should be  succeed
        #. move virtual firewall to firewallNode should return succeed
        #. remove ipaddress should return succeed
        #. add user1 to created cloudspace by user2 should return succeed
        #. delete user2 from created cloud space1 should return succeed
        #. destroy cloudspace1 by user2 should be succeed

        """
        self.lg("%s STARTED" % self._testID)
        self.user_group = ["admin", "level1"]
        self.lg("create user1 and user2  with level1 + admin group")
        self.user1 = self.cloudbroker_user_create(group=self.user_group)
        self.user2 = self.cloudbroker_user_create(group=self.user_group)

        self.lg("- create user1 %s with level1 and admin  domain " % self.user1)
        self.lg("- create user2 %s with level1 and admin  domain " % self.user2)

        self.user1_api = self.get_authenticated_user_api(self.user1)
        self.user2_api = self.get_authenticated_user_api(self.user2)
        self.lg("- create 2 cloudspaces one by user1 and another by user2")

        cloudspaceId1 = self.cloudbroker_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.user2,
            api=self.user2_api,
        )
        cloudspaceId2 = self.cloudbroker_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.user1,
            api=self.user1_api,
        )
        cloudspaceId3 = self.cloudbroker_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.user1,
            api=self.user1_api,
        )

        self.lg("- update cloudspace name by user1")

        response = self.user1_api.cloudbroker.cloudspace.update(
            cloudspaceId=cloudspaceId1, name=self.account_owner
        )
        self.assertTrue(response)

        self.lg("- deploy VFW")
        try:
            self.user1_api.cloudbroker.cloudspace.deployVFW(cloudspaceId=cloudspaceId1)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbbiden")
        self.lg("- start VFW")

        response = self.user1_api.cloudbroker.cloudspace.startVFW(
            cloudspaceId=cloudspaceId1
        )
        self.assertTrue(response)
        self.lg("- reset VFW")

        # Skip https://github.com/0-complexity/openvcloud/issues/706
        # try:
        #    self.user1_api.cloudbroker.cloudspace.resetVFW(cloudspaceId = cloudspaceId1)

        # except ApiError as e :
        #    self.lg('- expected error raised %s' % e.message)
        #   self.assertEqual(e.message, '403 Forbbiden')
        self.lg("- stop VFW")
        try:
            self.user1_api.cloudbroker.cloudspace.stopVFW(cloudspaceId=cloudspaceId1)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbbiden")
        self.lg("- destroy VFW")
        try:
            self.user1_api.cloudbroker.cloudspace.destroyVFW(cloudspaceId=cloudspaceId1)

        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbbiden")

        self.lg("- add user1 to cloudspace")

        response = self.user1_api.cloudbroker.cloudspace.addUser(
            cloudspaceId=cloudspaceId1, username=self.user1, accesstype="ARCXDU"
        )
        self.assertTrue(response)

        self.lg("- delete user2 from cloudspace1")

        response = self.user1_api.cloudbroker.cloudspace.deleteUser(
            cloudspaceId=cloudspaceId1, username=self.user2, recursivedelete="true"
        )
        self.assertTrue(response)

        self.lg("-destroy  cloudspace1")

        self.user2_api.cloudbroker.cloudspace.destroy(
            cloudspaceId=cloudspaceId1, reason="test", permanently=True
        )
        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspaceId1
        )

    def test003_level1_and_VMS(self):

        """ ACL-63
        *test case for user with level1+admin groups dealing with vms.*

        **Test Scenario:**

        #. create use1 and user2  with level1+admin group
        #. create machine 1 with user1 should succeed
        #. create machine 2 with user2 should succeed
        #. Add user2 to  vm1 by user2 should be succeed
        #. delete user2 from vm1 should return succeed
        #. start,then puase,then resume vm1 by user 2 should return succeed
        #. stop vm1 then reboot it by user2 should return succeed
        #. list machines in cloudspace by user2 should return succeed
        #. take snapshot in vm1 by user2  should succeed
        #.  Rollback virtual machine to a snapshot by user2 should succeed
        #. List snapshots of vm1 by user1 should succeed
        #. delete snapshot by user1 should succeed
        #. try checkvms API in diagnostics APIs should succeed
        #. try sync avaialble images to cloud broker should return succeed
        #. try Sync available sizes to Cloud Broker should return succeed
        """
        self.lg("%s STARTED" % self._testID)
        self.user_group = ["admin", "level1"]
        self.lg("create user1 and user2  with level1 + admin group")
        self.user1 = self.cloudbroker_user_create(group=self.user_group)
        self.user2 = self.cloudbroker_user_create(group=self.user_group)

        self.lg("- create user1 %s with level1 and admin  domain " % self.user1)
        self.lg("- create user2 %s with level1 and admin  domain " % self.user2)

        self.user1_api = self.get_authenticated_user_api(self.user1)
        self.user2_api = self.get_authenticated_user_api(self.user2)
        self.lg("- create cloudspace ")
        cloudspaceId1 = self.cloudbroker_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.account_owner,
            api=self.user1_api,
        )
        self.lg("- create VM1 by user1")
        machine1_id = self.cloudbroker_create_machine(
            cloudspace_id=cloudspaceId1, api=self.user1_api
        )
        self.lg("- create VM2 by user2")
        machine2_id = self.cloudbroker_create_machine(
            cloudspace_id=cloudspaceId1, api=self.user2_api
        )
        self.lg("- add user2 to vm1 ")
        response = self.user2_api.cloudbroker.machine.addUser(
            machineId=machine1_id, username=self.user2, accesstype="ARCXDU"
        )
        self.assertTrue(response)
        self.lg("- delete user2 from vm1")

        response = self.user2_api.cloudbroker.machine.deleteUser(
            machineId=machine1_id, username=self.user2
        )
        self.assertTrue(response)

        self.lg("start,then puase,then resume vm1 by user 2")

        self.user2_api.cloudbroker.machine.start(machineId=machine1_id, reason="test")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine1_id)["status"], "RUNNING"
        )
        self.user2_api.cloudbroker.machine.pause(machineId=machine1_id, reason="test")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine1_id)["status"], "PAUSED"
        )

        self.user2_api.cloudbroker.machine.resume(machineId=machine1_id, reason="test")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine1_id)["status"], "RUNNING"
        )
        self.lg("stop vm1 then reboot it by user2 ")

        self.user2_api.cloudbroker.machine.stop(machineId=machine1_id, reason="test")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine1_id)["status"], "HALTED"
        )

        self.user2_api.cloudbroker.machine.reboot(machineId=machine1_id, reason="test")
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine1_id)["status"], "RUNNING"
        )

        self.lg("list machines in cloudspace by user2")

        response = self.user2_api.cloudbroker.machine.list(cloudspaceId=cloudspaceId1)
        self.assertTrue(response)

        self.lg("take snapeshots")
        try:
            self.user2_api.cloudbroker.machine.snapshot(
                machineId=machine1_id, snapshotName=self.user1, reason="test"
            )

        except ApiError as e:
            self.lg("-expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("list snapeshots")

        self.listsnapshots = self.user2_api.cloudbroker.machine.listSnapshots(
            machineId=machine1_id, result="test"
        )
        self.assertTrue(self.listsnapshots)
        self.snapshot_name = self.listsnapshots[0]["name"]

        self.lg("Rollback virtual machine to a snapshot ")

        try:
            self.user2_api.cloudbroker.machine.stop(
                machineId=machine1_id, reason="test"
            )
            self.user2_api.cloudbroker.machine.rollbackSnapshot(
                machineId=machine1_id, name=self.snapshot_name, reason="test"
            )
        except ApiError as e:
            self.lg("-expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")
        self.lg("delete snapshot")
        try:
            self.user2_api.cloudbroker.machine.reboot(
                machineId=machine1_id, reason="test"
            )
            self.user2_api.cloudbroker.machine.deleteSnapshot(
                machineId=machine1_id, name=self.snapshot_name, reason="test"
            )

        except ApiError as e:
            self.lg("-expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("checkvms ")
        """
        try:
            response = self.user1_api.cloudbroker.diagnostics.checkVms() ##give unexpectederror
            self.assertTrue(response)
        except ApiError as e :
            self.lg('-expected error raised %s' % e.message)
            self.assertEqual(e.message,'403 Forbidden')

        """
