# coding=utf-8
import uuid
import unittest

from ....utils.utils import BasicACLTest
from JumpScale.portal.portal.PortalClient2 import ApiError


class ACLMACHINE(BasicACLTest):
    def setUp(self):
        super(ACLMACHINE, self).setUp()

        self.acl_setup()
        self.machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )


class Read(ACLMACHINE):
    def test003_machine_get_list(self):
        """ ACL-52
        *Test case for get/list machine api with user has read access on machine level.*

        **Test Scenario:**

        #. try to get machine with new user [user], should return 403
        #. try to list machines with new user [user], should return 403
        #. add user to the machine with read access
        #. get machine with new user [user], should succeed
        #. get cloudspace of the machine with new user [user], hould succeed
        #. get account of the machine with new user [user], hould succeed
        #. list machines with new user [user], should succeed
        #. create new machine with user2, should succeed
        #. get machine with user2, should succeed
        #. list machines with new user [user] still see 2 machine, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- try to get machine with new user [user], should return 403")
        try:
            self.user_api.cloudapi.machines.get(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- try to list machines with new user [user], should return 403")
        try:
            self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with read access")
        accesstype = "R"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- get machine with new user [user], should succeed")
        machine = self.user_api.cloudapi.machines.get(machineId=self.machine_id)
        self.assertEqual(machine["id"], self.machine_id)

        self.lg("- get cloudspace of the machine with new user [user], should succeed")
        cloudspace = self.user_api.cloudapi.cloudspaces.get(
            cloudspaceId=machine["cloudspaceid"]
        )
        self.assertEqual(cloudspace["id"], machine["cloudspaceid"])

        self.lg("- get account of the machine  with new user [user], should succeed")
        account = self.user_api.cloudapi.accounts.get(accountId=cloudspace["accountId"])
        self.assertEqual(account["id"], cloudspace["accountId"])

        self.lg("- list machines with new user [user], should succeed")
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 1)
        self.assertEqual(machines[0]["id"], self.machine_id)

        self.lg("- create new machine with user2, should succeed")
        new_machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )
        self.lg("- get machine with user2, should succeed")
        new_machine = self.account_owner_api.cloudapi.machines.get(
            machineId=new_machine_id
        )
        self.assertEqual(new_machine["id"], new_machine_id)

        self.lg(
            "- list machines with new user [user] still see 2 machine, should succeed"
        )
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 2)
        self.assertEqual(machines[0]["id"], self.machine_id)

        self.lg("%s ENDED" % self._testID)

    def test004_machine_getConsoleUrl_listSnapshots_getHistory(self):
        """ ACL-53
        *Test case for getConsoleUrl/listSnapshots/getHistory machine api with user has read access on machine level.*

        **Test Scenario:**

        #. try to getConsoleUrl machine with new user [user], should return 403
        #. create snapshot for a machine with the account user, should succeed
        #. try to listSnapshots of created machine with new user [user], should return 403
        #. try to getHistory of created machine with new user [user], should return 403
        #. add user to the machine with read access
        #. getConsoleUrl machine with new user [user], should succeed
        #. listSnapshots of created machine with new user [user], should succeed
        #. getHistory of created machine with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(
            "- try to getConsoleUrl machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.getConsoleUrl(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- create snapshot for a machine with the account user, should succeed")
        name = str(uuid.uuid4()).replace("-", "")[0:10]
        self.account_owner_api.cloudapi.machines.snapshot(
            machineId=self.machine_id, name=name
        )
        snapshot = self.api.cloudapi.machines.listSnapshots(machineId=self.machine_id)[
            0
        ]
        self.assertEqual(snapshot["name"], name)

        self.lg(
            "- try to listSnapshots of created machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.listSnapshots(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg(
            "- try to getHistory of created machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.getHistory(
                machineId=self.machine_id, size=1
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with read access")
        accesstype = "R"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- getConsoleUrl machine with new user [user], should succeed")
        consol_url = self.user_api.cloudapi.machines.getConsoleUrl(
            machineId=self.machine_id
        )
        self.assertTrue(consol_url)

        self.lg(
            "- listSnapshots of created machine with new user [user], should succeed"
        )
        snapshots = self.user_api.cloudapi.machines.listSnapshots(
            machineId=self.machine_id
        )
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["name"], name)

        self.lg("- getHistory of created machine with new user [user], should succeed")
        histories = self.user_api.cloudapi.machines.getHistory(
            machineId=self.machine_id, size=10
        )

        self.assertIn(
            "User {} called machines/create".format(self.account_owner),
            [history["message"] for history in histories],
        )
        self.assertIn(
            "User {} called machines/snapshot".format(self.account_owner),
            [history["message"] for history in histories],
        )

        self.lg("%s ENDED" % self._testID)


class Write(ACLMACHINE):
    def test003_machine_start_stop_reboot_reset(self):
        """ ACL-40
        *Test case for start/stop/reboot/reset machine api with user has write access on machine level.*

        **Test Scenario:**

        #. try to stop machine with new user [user], should return 403
        #. try to reboot machine with new user [user], should return 403
        #. try to reset machine with new user [user], should return 403
        #. stop machine with the account user, should succeed
        #. try to start machine with new user [user], should return 403
        #. add user to the machine with write access
        #. start machine with new user [user], should succeed
        #. reboot machine with new user [user], should succeed
        #. reset machine with new user [user], should succeed
        #. stop machine with new user [user], should succeed
        #. start machine with new user [user], should succeed
        #. disable the machine account and check the machine status, should be Halted
        #. enable the machine account and check the machine status, should be Halted
        #. start machine with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- try to stop machine with new user [user], should return 403 ")
        try:
            self.user_api.cloudapi.machines.stop(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- try to reboot machine with new user [user], should return 403 ")
        try:
            self.user_api.cloudapi.machines.reboot(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- try to reset machine with new user [user], should return 403 ")
        try:
            self.user_api.cloudapi.machines.reset(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- stop machine with the account user, should succeed")
        self.account_owner_api.cloudapi.machines.stop(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg("- try to start machine with new user [user], should return 403 ")
        try:
            self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with write access")
        accesstype = "CRX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- reboot machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.reboot(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- reset machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.reset(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- stop machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.stop(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg(
            "- disable the machine account and check the machine status, should be Halted"
        )
        self.api.cloudbroker.account.disable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg(
            "- enable the machine account and check the machine status, should be Halted"
        )
        self.api.cloudbroker.account.enable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("%s ENDED" % self._testID)

    def test004_machine_pause_resume(self):
        """ ACL-41
        *Test case for pause/resume machine api with user has write access on machine level.*

        **Test Scenario:**

        #. try to pause machine with new user [user], should return 403
        #. pause machine with the account user, should succeed
        #. try to resume machine with new user [user], should return 403
        #. add user to the machine with write access
        #. resume machine with new user [user], should succeed
        #. pause machine with new user [user], should succeed
        #. disable the machine account and check the machine status, should be Halted
        #. enable the machine account and check the machine status, should be Halted
        #. start machine with new user [user], should succeed
        #. pause machine with new user [user], should succeed
        #. resume machine with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- try to pause machine with new user [user], should return 403")
        try:
            self.user_api.cloudapi.machines.pause(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- pause machine with the account user, should succeed")
        self.account_owner_api.cloudapi.machines.pause(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "PAUSED",
        )

        self.lg("- try to resume machine with new user [user], should return 403")
        try:
            self.user_api.cloudapi.machines.resume(machineId=self.machine_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with write access")
        accesstype = "CRX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- resume machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.resume(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- pause machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.pause(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "PAUSED",
        )

        self.lg(
            "- disable the machine account and check the machine status, should be Halted"
        )
        self.api.cloudbroker.account.disable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg(
            "- enable the machine account and check the machine status, should be Halted"
        )
        self.api.cloudbroker.account.enable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- pause machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.pause(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "PAUSED",
        )

        self.lg("- resume machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.resume(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("%s ENDED" % self._testID)

    def test005_machine_snapshot_create_rollback_delete(self):
        """ ACL-42
        *Test case for snapshot create/rollback/delete machine api with user has write access on machine level.*

        **Test Scenario:**

        #. try to create snapshot for a machine with new user [user], should return 403
        #. create snapshot for a machine with the account user, should succeed
        #. stop machine with account user, should succeed
        #. try to rollback snapshot for a machine with new user [user], should return 403
        #. try to delete snapshot for a machine with new user [user], should return 403
        #. add user to the machine with write access
        #. start machine with new user [user], should succeed
        #. create snapshot for a machine with new user [user], should succeed
        #. stop machine with new user [user], should succeed
        #. rollback snapshot for a machine with new user [user], should succeed
        #. start machine with new user [user], should succeed
        #. delete snapshot for a machine with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(
            "- try to create snapshot for a machine with new user [user], should return 403"
        )
        first_name = str(uuid.uuid4()).replace("-", "")[0:10]
        try:
            self.user_api.cloudapi.machines.snapshot(
                machineId=self.machine_id, name=first_name
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- create snapshot for a machine with the account user, should succeed")
        self.account_owner_api.cloudapi.machines.snapshot(
            machineId=self.machine_id, name=first_name
        )
        first_snapshot = self.api.cloudapi.machines.listSnapshots(
            machineId=self.machine_id
        )[0]
        self.assertEqual(first_snapshot["name"], first_name)

        self.lg("- stop machine with account user, should succeed")
        self.account_owner_api.cloudapi.machines.stop(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg(
            "- try to rollback snapshot for a machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.rollbackSnapshot(
                machineId=self.machine_id, name=first_snapshot["name"]
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg(
            "- try to delete snapshot for a machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.deleteSnapshot(
                machineId=self.machine_id, name=first_snapshot["name"]
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with write access")
        accesstype = "CRX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- create snapshot for a machine with new user [user], should succeed")
        second_name = str(uuid.uuid4()).replace("-", "")[0:10]
        self.account_owner_api.cloudapi.machines.snapshot(
            machineId=self.machine_id, name=second_name
        )
        snapshots = self.api.cloudapi.machines.listSnapshots(machineId=self.machine_id)
        self.assertEqual(len(snapshots), 2)
        self.assertIn(second_name, [snapshot["name"] for snapshot in snapshots])
        self.assertIn(first_name, [snapshot["name"] for snapshot in snapshots])
        second_snapshot = [
            snapshot for snapshot in snapshots if second_name == snapshot["name"]
        ][0]

        self.lg("- stop machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.stop(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "HALTED",
        )

        self.lg(
            "- rollback snapshot for a machine with new user [user], should succeed"
        )
        self.user_api.cloudapi.machines.rollbackSnapshot(
            machineId=self.machine_id, name=first_snapshot["name"]
        )

        self.lg("- start machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.start(machineId=self.machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["status"],
            "RUNNING",
        )

        self.lg("- delete snapshot for a machine with new user [user], should succeed")
        self.user_api.cloudapi.machines.deleteSnapshot(
            machineId=self.machine_id, name=second_snapshot["name"]
        )

        snapshots = self.api.cloudapi.machines.listSnapshots(machineId=self.machine_id)
        self.assertEqual(len(snapshots), 1)
        self.assertNotIn(second_name, [snapshot["name"] for snapshot in snapshots])
        self.assertEqual(first_name, snapshots[0]["name"])

        self.lg("%s ENDED" % self._testID)

    def test006_machine_update(self):
        """ ACL-43
        *Test case for update machine api with user has write access on machine level.*

        **Test Scenario:**

        #. try to update machine name with new user [user], should return 403
        #. add user to the machine with write access
        #. update machine name with new user [user], should succeed
        #. update machine description with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- try to update machine name with new user [user], should return 403")
        name = str(uuid.uuid4()).replace("-", "")[0:10]
        try:
            self.user_api.cloudapi.machines.update(machineId=self.machine_id, name=name)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("- add user to the machine with write access")
        accesstype = "CRX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("- update machine name with new user [user], should succeed")
        self.user_api.cloudapi.machines.update(machineId=self.machine_id, name=name)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["name"], name
        )

        self.lg("- update machine description with new user [user], should succeed")
        self.user_api.cloudapi.machines.update(
            machineId=self.machine_id, description=name
        )
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=self.machine_id)["description"],
            name,
        )

        self.lg("%s ENDED" % self._testID)


class Admin(ACLMACHINE):
    def test003_machine_add_update_delete_User(self):
        """ ACL-44
        *Test case for add/update/delete user api with user has admin access on machine level.*

        **Test Scenario:**

        #. add user2 to the machine with admin access
        #. create user3
        #. add user3 to the created machine by user2 with read access, should succeed
        #. update user3 access on machine by user2 with write access, should succeed
        #. delete machine user3 with user1, should succeed
        #. get machine users, user3 not in the returened list
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- add user2 to the machine with admin access")
        accesstype = "ACDRUX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("2- create user3")
        user3 = self.cloudbroker_user_create()

        self.lg(
            "3- add user3 to the created machine by user2 with read access, should succeed"
        )
        self.user_api.cloudapi.machines.addUser(
            machineId=self.machine_id, userId=user3, accesstype="R"
        )
        machine = self.api.cloudapi.machines.get(self.machine_id)
        self.assertIn(user3, [acl["userGroupId"] for acl in machine["acl"]])
        acl_user3 = [acl for acl in machine["acl"] if acl["userGroupId"] == user3][0]
        self.assertEqual(acl_user3["right"], "R")

        self.lg(
            "4- update user3 access on machine by user2 with write access, should succeed"
        )
        self.user_api.cloudapi.machines.updateUser(
            machineId=self.machine_id, userId=user3, accesstype="CRX"
        )
        machine = self.api.cloudapi.machines.get(self.machine_id)
        self.assertIn(user3, [acl["userGroupId"] for acl in machine["acl"]])
        acl_user3 = [acl for acl in machine["acl"] if acl["userGroupId"] == user3][0]
        self.assertEqual(acl_user3["right"], "CRX")

        self.lg("5- delete machine user3 with user1, should succeed")
        self.user_api.cloudapi.machines.deleteUser(
            machineId=self.machine_id, userId=user3
        )

        self.lg("6- get machine users, user3 not in the returened list")
        machine = self.api.cloudapi.machines.get(self.machine_id)
        self.assertNotIn(user3, [acl["userGroupId"] for acl in machine["acl"]])

        self.lg("%s ENDED" % self._testID)

    def test004_machine_add_update_delete_User_wrong(self):
        """ ACL-45
        *Test case for add/update/delete user api wrong with user has admin access on machine level.*

        **Test Scenario:**

        #. add user2 to the cloudspace created by user1 as admin
        #. create user3
        #. use username not_registered_user which not exists
        #. try add not_registered_user to the machine by admin user with read access, should return 404
        #. try update not_registered_user access on machine by admin user with write access, should return 404
        #. try update user3 access on machine by admin user with write access, should return 404
        #. try delete machine not_registered_user with admin user, should return 404
        #. try to delete user3 from the machine using admin user api, should return 404
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- add user to the machine with admin access")
        accesstype = "ACDRUX"
        self.lg(
            "- add user1 to the machine owned by user2 with access type [%s]"
            % accesstype
        )
        self.add_user_to_machine(
            machine_id=self.machine_id, user=self.user, accesstype=accesstype
        )

        self.lg("2- create user3")
        user3 = self.cloudbroker_user_create()

        self.lg("3- use username not_registered_user which not exists")
        not_registered_user = str(uuid.uuid4()).replace("-", "")[
            0:10
        ]  # non registered user

        self.lg(
            "4- try add not_registered_user to the machine by admin user with read access"
        )
        try:
            self.user_api.cloudapi.machines.addUser(
                machineId=self.machine_id, userId=not_registered_user, accesstype="R"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg(
            "5- try update not_registered_user access on machine by admin user with write access"
        )
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=self.machine_id, userId=not_registered_user, accesstype="RCX"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("- get machine users, not_registered_user not in the returened list")
        machine = self.api.cloudapi.machines.get(self.machine_id)
        self.assertNotIn(
            not_registered_user, [acl["userGroupId"] for acl in machine["acl"]]
        )

        self.lg("6- try update user3 access on machine by admin user with write access")
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=self.machine_id, userId=user3, accesstype="RCX"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("- get machine users, user3 not in the returened list")
        machine = self.api.cloudapi.machines.get(self.machine_id)
        self.assertNotIn(user3, [acl["userGroupId"] for acl in machine["acl"]])

        self.lg("7- try delete machine not_registered_user with admin user")
        try:
            self.user_api.cloudapi.machines.deleteUser(
                machineId=self.machine_id, userId=not_registered_user
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("8- try to delete user3 from the machine using admin user api")
        try:
            self.user_api.cloudapi.machines.deleteUser(
                machineId=self.machine_id, userId=user3
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("%s ENDED" % self._testID)
