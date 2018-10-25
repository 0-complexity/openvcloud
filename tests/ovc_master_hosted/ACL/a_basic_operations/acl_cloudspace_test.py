# coding=utf-8
from time import sleep
import random
import unittest
import uuid
from socket import error as VMConnectionError
from ....utils.utils import BasicACLTest
from JumpScale import j
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from nose_parameterized import parameterized


class ACLCLOUDSPACE(BasicACLTest):
    def setUp(self):
        super(ACLCLOUDSPACE, self).setUp()

        self.acl_setup()


class Read(ACLCLOUDSPACE):
    def test003_cloudspace_get_with_readonly_user(self):
        """ ACL-18
        *Test case for cloudspace get api with user has read only access.*

        **Test Scenario:**

        #. get cloudspace1 with user1
        #. try get cloudspace1 with user2, should fail '403 Forbidden'
        #. add user1 to the cloudspace owned by user2
        #. get cloudspace1 with user1, should succeed
        #. get account with user1
        #. delete account.
        #. get account2 with user1, should fail '404 Not Found'
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- create cloudspace with user1")
        self._cloudspaces = []
        cloudspace_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )
        self.lg("1- get cloudspace with user1")
        cloudspace1 = self.account_owner_api.cloudapi.cloudspaces.get(
            cloudspaceId=cloudspace_id
        )
        self.assertEqual(cloudspace1["id"], cloudspace_id)

        self.lg("2- try get cloudspace1 with user2")
        try:
            self.user_api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("3- add user1 to the cloudspace owned by user2")
        self.api.cloudapi.cloudspaces.addUser(
            cloudspaceId=cloudspace_id, userId=self.user, accesstype="R"
        )

        self.lg("4- get cloudspace2 with user1")
        cloudspace1 = self.user_api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        self.assertEqual(cloudspace1["id"], cloudspace_id)

        self.lg("5- get account with user1")
        account = self.user_api.cloudapi.accounts.get(
            accountId=cloudspace1["accountId"]
        )
        self.assertEqual(account["id"], cloudspace1["accountId"])

        self.lg("6- delete account: %s" % self.account_id)
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="testing", permanently=True
        )
        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )
        self.CLEANUP["accountId"].remove(self.account_id)

        self.lg("7- get cloudspace2 with user1")
        try:
            self.user_api.cloudapi.cloudspaces.get(cloudspaceId=cloudspace_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("%s ENDED" % self._testID)

    def test006_cloudspace_list_with_another_cloudspace(self):
        """ ACL-14
        *Test case for cloud space list API with user has read only access.*

        **Test Scenario:**

        #. Create new cloud space for account owner
        #. List cloud spaces with account owner , should return list with 2 cloud spaces
        #. Try list user's cloud spaces, should return empty list
        #. Give the user read access to the newly created cloud space
        #. Try list user's cloud spaces, should return list with 1 cloud space
        #. Verify that 'ACL' rights for the account owner is ACDRUX and for user is R only
        #. Create another cloud space
        #. Try list user's cloud spaces, should return list with 1 cloud space
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- Create new cloud space")
        cloudspace_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )
        self.lg("2- List account owner cloud spaces")
        cloudspaces = self.account_owner_api.cloudapi.cloudspaces.list()
        self.assertEqual(
            len(cloudspaces), 2, "Failed to list all account owner cloud spaces!"
        )

        self.lg("3- Try list user's cloud spaces")
        self.assertFalse(
            self.user_api.cloudapi.cloudspaces.list(), "This list should be empty!"
        )

        self.lg("4- Give the user read access to 1 cloud space")
        self.account_owner_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=cloudspace_id, userId=self.user, accesstype="R"
        )

        self.lg("5- Try list user's cloud spaces,")
        cloudspaces = self.user_api.cloudapi.cloudspaces.list()
        self.assertEqual(len(cloudspaces), 2, "Failed to list all user's cloud spaces!")
        self.lg(
            "6- Verify that ACL rights for the account owner is ACDRUX and for user is R only"
        )
        acl = cloudspaces[0]["acl"]
        self.assertEqual(len(acl), 2)
        self.assertTrue(
            filter(
                lambda e: e["userGroupId"] == self.account_owner
                and set(e["right"]) == set("ACDRUX"),
                acl,
            )
        )
        self.assertTrue(
            filter(lambda e: e["userGroupId"] == self.user and e["right"] == "R", acl)
        )

        self.lg("7- Create another cloud space")
        self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )

        self.lg("8- Try list user's cloud spaces,")
        cloudspaces = self.user_api.cloudapi.cloudspaces.list()
        self.assertEqual(len(cloudspaces), 3, "Failed to list all user's cloud spaces!")

        self.lg("%s ENDED" % self._testID)

    def test007_cloudspace_list_deleted_cloudspace(self):
        """ ACL-15
        *Test case for cloud space list API with user has read only access.*

        **Test Scenario:**

        #. Create new cloud space for account owner
        #. Give the user read access to the the newly created cloud space
        #. Try list user's cloud spaces, should return list with 1 cloud space
        #. Delete the newly created cloud space
        #. Try list user's cloud spaces, should return empty list
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- Create new cloud space")
        cloudspace_id = self.cloudapi_cloudspace_create(
            self.account_id, self.location, self.account_owner
        )

        self.lg("2- Give the user read access to 1 cloud space")
        self.account_owner_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=cloudspace_id, userId=self.user, accesstype="R"
        )

        self.lg("3- Try list user's cloud spaces,")
        cloudspaces = self.user_api.cloudapi.cloudspaces.list()
        self.assertEqual(len(cloudspaces), 2, "Failed to list all user's cloud spaces!")

        self.lg("4- Delete the newly created cloud space")
        self.account_owner_api.cloudapi.cloudspaces.delete(
            cloudspaceId=cloudspace_id, permanently=True
        )

        self.lg("5- Try list user's cloud spaces,")
        cloudspaces = self.user_api.cloudapi.cloudspaces.list()
        self.assertEqual(len(cloudspaces), 1)

        self.lg("%s ENDED" % self._testID)

    def test008_cloudspace_disabled_deleted_account(self):
        """ ACL-16
        *Test case for cloud space list API with user has read only access.*

        **Test Scenario:**

        #. Give the user read access to the 1 cloud space created by the account owner
        #. Disable the account and try list user's cloud spaces, Should return list of existing users on the account
        #. Re-enable the account and try list user's cloud spaces,
           should return list with 1 cloud space
        #. Delete the account and try list user's cloud spaces, should return empty list
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- Give the user read access to 1 cloud space")
        cloudspace_id = self.account_owner_api.cloudapi.cloudspaces.list()[0]["id"]
        self.account_owner_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=cloudspace_id, userId=self.user, accesstype="R"
        )

        self.lg("2- Disable the account")
        self.api.cloudbroker.account.disable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        self.assertTrue(
            self.user_api.cloudapi.cloudspaces.list(),
            "Should return list of existing users on the account",
        )

        self.lg("3- Re-enable the account")
        self.api.cloudbroker.account.enable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        cloudspaces = self.user_api.cloudapi.cloudspaces.list()
        self.assertEqual(len(cloudspaces), 1, "Failed to list all user's cloud spaces!")

        self.lg("4- Delete the account")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test %s" % self._testID, permanently=True
        )
        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )
        self.CLEANUP["accountId"].remove(self.account_id)
        self.assertFalse(
            self.user_api.cloudapi.cloudspaces.list(), "This list should be empty!"
        )

        self.lg("%s ENDED" % self._testID)

    def test009_machine_list_deleted_machine(self):
        """ ACL-17
        *Test case for machine list API with user has read only access.*

        **Test Scenario:**

        #. Create 1 machine for account owner
        #. List account owner machines, should return list with 1 machine
        #. Try list user's machines, should return empty list
        #. Give the user read access to the newly created machine
        #. Try list user's machines, should return list with 1 machine
        #. Delete the machine and try list user's cloud spaces, should return empty list
        """
        self.lg("%s STARTED" % self._testID)
        self.lg("1- Create 1 machine for account owner")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )
        self.lg("2- List account owner machines")
        machines = self.account_owner_api.cloudapi.machines.list(
            cloudspaceId=self.cloudspace_id
        )
        self.assertEqual(len(machines), 1, "Failed to list all account owner machines!")

        self.lg("3- Try list user's machines, should return empty list")
        self.assertFalse(
            self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        )

        self.lg("4- Give the user read access to the newly created machine")
        self.account_owner_api.cloudapi.machines.addUser(
            machineId=machine_id, userId=self.user, accesstype="R"
        )

        self.lg("5- Try list user's machines, should return list with 1 machine")
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 1, "Failed to list all account owner machines!")

        self.lg("6- Delete the machine")
        self.account_owner_api.cloudapi.machines.delete(
            machineId=machine_id, permanently=True
        )
        self.assertFalse(
            self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        )

        self.lg("%s ENDED" % self._testID)

    def test010_machine_list_deleted_cloudspace(self):
        """ ACL-19
        *Test case for machine list API with user has read only access.*

        **Test Scenario:**

        #. Create 1 machine for account owner
        #. Give the user read access to the newly created machine
        #. Try list user's machines, should return list with 1 machine
        #. Delete the clouds pace and try list user's cloud spaces, should return empty list
        """
        self.lg("%s STARTED" % self._testID)
        self._machine_list_scenario_base()

        self.lg("4- Delete the cloud space")
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id,
            reason="Test %s" % self._testID,
            permanently=True,
        )

        self.wait_for_status(
            "DESTROYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )
        # This is a temp fix to workaround CB-855
        for _ in xrange(10):
            if not self.user_api.cloudapi.machines.list(
                cloudspaceId=self.cloudspace_id
            ):
                break
            sleep(1)

        self.assertFalse(
            self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        )

        self.lg("%s ENDED" % self._testID)

    def test011_machine_list_disabled_deleted_account(self):
        """ ACL-20
        *Test case for machine list API with user has read only access.*

        **Test Scenario:**

        #. Create 1 machine for account owner
        #. Give the user read access to the newly created machine
        #. Try list user's machines, should return list with 1 machine
        #. Disable the account and try list user's machines, should return list
        #. Re-enable the account and try list user's machines, should return list with 1 machines
        #. Delete the account and try list user's machines, should return empty list

        """
        self.lg("%s STARTED" % self._testID)
        self._machine_list_scenario_base()

        self.lg("4- Disable the account")
        self.api.cloudbroker.account.disable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 1, "Failed to list all account owner machines!")

        self.lg("5- Re-enable the account")
        self.api.cloudbroker.account.enable(
            accountId=self.account_id, reason="Test %s" % self._testID
        )
        machines = self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        self.assertEqual(len(machines), 1, "Failed to list all account owner machines!")

        self.lg("6- Delete the account")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test %s" % self._testID, permanently=True
        )
        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )
        self.CLEANUP["accountId"].remove(self.account_id)
        # This is a temp fix to workaround CB-855
        for _ in xrange(10):
            if not self.user_api.cloudapi.machines.list(
                cloudspaceId=self.cloudspace_id
            ):
                break
            sleep(1)

        self.assertFalse(
            self.user_api.cloudapi.machines.list(cloudspaceId=self.cloudspace_id)
        )
        self.lg("%s ENDED" % self._testID)

    def test012_portforwarding_list(self):
        """ ACL-30
        *Test case for portforwaring list API with user has read access.*

        **Test Scenario:**

        #. Create 1 machine for account owner
        #. Try to list portforwarding with new user [user], should return 403
        #. Give the user read access to the newly created machine
        #. List portforwarding with new user [user], should return 0 portforwarding
        #. Create one portforwarding
        #. List portforwarding with new user [user], should return 1 portforwarding
        #. Delete the created portforwarding
        #. List portforwarding with new user [user], should return 0 portforwarding

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- Create 1 machine for account owner")
        machine_id = self.cloudapi_create_machine(
            cloudspace_id=self.cloudspace_id, api=self.account_owner_api, wait=False
        )
        self.lg("2- Try to list portforwarding with new user [user], should return 403")
        try:
            self.user_api.cloudapi.portforwarding.list(
                cloudspaceId=self.cloudspace_id, machineId=machine_id
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("3- Give the user read access to the newly created machine")
        self.account_owner_api.cloudapi.machines.addUser(
            machineId=machine_id, userId=self.user, accesstype="R"
        )

        self.lg(
            "4- List portforwarding with new user [user], should return 0 portforwarding"
        )
        sleep(2)
        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding), 0, "Failed to list all cloudspace port forwarding!"
        )

        self.lg("5- Create one portforwarding")
        self.add_portforwarding(machine_id=machine_id)
        self.lg(
            "6- List portforwarding with new user [user], should return 1 portforwarding"
        )
        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding), 1, "Failed to list all cloudspace port forwarding!"
        )

        self.lg("7- Delete the created portforwarding")
        portforwarding_id = portforwarding[0]["id"]
        pcl = j.clients.portal.getByInstance("main")
        pcl.actors.cloudapi.portforwarding.delete(
            cloudspaceId=self.cloudspace_id, id=portforwarding_id
        )

        self.lg(
            "8- List portforwarding with new user [user], should return 0 portforwarding"
        )
        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding), 0, "Failed to list all cloudspace port forwarding!"
        )

        self.lg("%s ENDED" % self._testID)


class Write(ACLCLOUDSPACE):
    def test003_cloudspace_deploy_getDefenseShield(self):
        """ ACL-31
        *Test case for deploy/getDefenseShield cloudspace api with user has write access on cloud space level.*

        **Test Scenario:**

        #. try to deploy cloudspace with new user [user], should return 403
        #. add user to the cloudspace created by user1 with write access
        #. deploy cloudspace with new user [user], should succeed
        #. create new user [new_user]
        #. try to get Defense Shield of cloudspace with new user [new_user], should return 403
        #. add new_user to the cloudspace created by user1 with write access
        #. get Defense Shield of cloudspace with new user [new_user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- try to deploy cloudspace with new user [user], should return 403")
        try:
            self.user_api.cloudapi.cloudspaces.deploy(cloudspaceId=self.cloudspace_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("2- add user to the cloudspace created by user1 with write access")
        self.add_user_to_cloudspace(
            cloudspace_id=self.cloudspace_id, user=self.user, accesstype="CRX"
        )

        self.lg("3- deploy cloudspace with new user [user], should succeed")
        self.user_api.cloudapi.cloudspaces.deploy(cloudspaceId=self.cloudspace_id)
        self.wait_for_status(
            "DEPLOYED",
            self.account_owner_api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("4- create new user [new_user]")
        new_user = self.cloudbroker_user_create()
        new_user_api = self.get_authenticated_user_api(new_user)

        self.lg(
            "5- try to get Defense Shield of cloudspace with new user [new_user], should return 403"
        )
        try:
            new_user_api.cloudapi.cloudspaces.getDefenseShield(
                cloudspaceId=self.cloudspace_id
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("6- add new_user to the cloudspace created by user1 with write access")
        self.add_user_to_cloudspace(
            cloudspace_id=self.cloudspace_id, user=new_user, accesstype="CRX"
        )

        self.lg(
            "7- get Defense Shield of cloudspace with new user [new_user], should succeed"
        )
        defense_shield = new_user_api.cloudapi.cloudspaces.getDefenseShield(
            cloudspaceId=self.cloudspace_id
        )
        [
            self.assertIn(key, defense_shield.keys())
            for key in ["url", "user", "password"]
        ]
        self.assertEqual(defense_shield["user"], "admin")

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["byId", "byPort"])
    def test004_cloudspace_portforwarding_add_update_delete(self, method):
        """ ACL-32
        *Test case for add/update/delete portforwarding api with user has write access on cloud space level.*

        **Test Scenario:**

        #. Create 1 machine for account owner.
        #. Add user to the cloudspace with write access.
        #. Create one portforwarding, should succeed.
        #. Update portforwarding with new ports, should succeed.
        #. Try to connect to the virtual machine (VM1), should succeed.
        #. Try to connect to the virtual machine (VM1) using the old public port, should fail
        #. Try update port with non vaild port.
        #. Delete cloudspace user2 with user1, should succeed.
        #. Try delete non exists portforwarding, should fail '403 Forbidden'.
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("Create 1 machine for account owner")
        machine_id = self.cloudapi_create_machine(
            cloudspace_id=self.cloudspace_id, api=self.account_owner_api
        )

        self.lg("Add user to the cloudspace created by user1 with write access")
        self.add_user_to_cloudspace(
            cloudspace_id=self.cloudspace_id, user=self.user, accesstype="CRX"
        )

        self.lg("Create one portforwarding")
        public_port = random.randint(1000, 65000)
        vm_port = 22
        self.add_portforwarding(
            machine_id=machine_id,
            api=self.user_api,
            cs_publicport=public_port,
            vm_port=vm_port,
        )

        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding),
            1,
            "Failed to get the port forwarding for machine[%s]" % machine_id,
        )

        self.lg("Try to connect to the virtual machine (VM1), should succeed")
        self.assertTrue(self.check_vm(machine_id, port=public_port))

        self.lg("4- Update portforwarding with new ports")
        portforwarding_id = portforwarding[0]["id"]
        cs_publicip = portforwarding[0]["publicIp"]
        new_public_port = random.randint(1000, 65000)

        if method == "byPort":
            self.user_api.cloudapi.portforwarding.updateByPort(
                cloudspaceId=self.cloudspace_id,
                sourcePublicIp=cs_publicip,
                sourcePublicPort=public_port,
                sourceProtocol="tcp",
                machineId=machine_id,
                publicIp=cs_publicip,
                publicPort=new_public_port,
                localPort=vm_port,
                protocol="tcp",
            )

        elif method == "byId":
            self.user_api.cloudapi.portforwarding.update(
                cloudspaceId=self.cloudspace_id,
                id=portforwarding_id,
                machineId=machine_id,
                publicIp=cs_publicip,
                publicPort=new_public_port,
                localPort=vm_port,
                protocol="tcp",
            )

        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding),
            1,
            "Failed to get the port forwarding for machine[%s]" % machine_id,
        )
        self.assertEqual(int(portforwarding[0]["publicPort"]), new_public_port)
        self.assertEqual(int(portforwarding[0]["localPort"]), vm_port)

        self.lg("Try to connect to the virtual machine (VM1), should succeed")
        self.assertTrue(self.check_vm(machine_id, port=new_public_port))

        self.lg(
            "Try to connect to the virtual machine (VM1) using the old public port, should fail"
        )
        
        self.assertFalse(self.check_vm(machine_id, port=public_port, timeout=5))

        # skip https://github.com/0-complexity/openvcloud/issues/606
        # self.lg('5- try update port with non vaild port')
        # with self.assertRaises(ApiError) as e:
        #     if method == 'byPort':
        #         self.user_api.cloudapi.portforwarding.updateByPort(cloudspaceId=self.cloudspace_id,
        #                                                             sourcePublicIp=cs_publicip,
        #                                                             sourcePublicPort=public_port,
        #                                                             sourceProtocol='tcp',
        #                                                             machineId=machine_id,
        #                                                             publicIp=cs_publicip,
        #                                                             publicPort=new_public_port,
        #                                                             localPort=1000000000,
        #                                                             protocol='tcp')
        #     elif method == 'byId':
        #         self.user_api.cloudapi.portforwarding.update(cloudspaceId=self.cloudspace_id,
        #                                                     id=portforwarding_id,
        #                                                     machineId=machine_id,
        #                                                     publicIp=cs_publicip,
        #                                                     publicPort=new_public_port,
        #                                                     localPort=1000000000,
        #                                                     protocol='tcp')

        # self.assertEqual(e.exception.message, '400 Bad Request')

        self.lg("Delete portforwarding")
        if method == "byPort":
            self.user_api.cloudapi.portforwarding.deleteByPort(
                cloudspaceId=self.cloudspace_id,
                publicIp=cs_publicip,
                publicPort=new_public_port,
                protocol="tcp",
            )

        elif method == "byId":
            self.user_api.cloudapi.portforwarding.delete(
                cloudspaceId=self.cloudspace_id, id=portforwarding_id
            )

        portforwarding = self.user_api.cloudapi.portforwarding.list(
            cloudspaceId=self.cloudspace_id, machineId=machine_id
        )
        self.assertEqual(
            len(portforwarding),
            0,
            "No port forwarding should be listed on this cloud space anymore",
        )

        self.lg("Try delete non exists portforwarding")
        with self.assertRaises(ApiError) as e:
            if method == "byPort":
                fake_port = random.randint(1000, 65000)
                self.user_api.cloudapi.portforwarding.deleteByPort(
                    cloudspaceId=self.cloudspace_id,
                    publicIp=cs_publicip,
                    publicPort=fake_port,
                    protocol="tcp",
                )

            elif method == "byId":
                self.user_api.cloudapi.portforwarding.delete(
                    cloudspaceId=self.cloudspace_id, id=portforwarding_id
                )

        self.assertEqual(e.exception.message, "404 Not Found")

        self.lg("%s ENDED" % self._testID)

    def test005_cloudspace_create_clone_delete_machine(self):
        """ ACL-33
        *Test case for create/clone/delete machine api with user has write access on cloud space level.*

        **Test Scenario:**

        #. create 1 machine for account owner
        #. try to create machine with new user [user], should return 403
        #. try to clone created machine with new user [user], should return 403
        #. try to delete created machine with new user [user], should return 403
        #. add user to the cloudspace with write access
        #. create machine with new user [user], should succeed
        #. clone created machine with new user [user], should succeed
        #. delete created machine with new user [user], should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- create 1 machine for account owner")
        owner_machine_id = self.cloudapi_create_machine(
            cloudspace_id=self.cloudspace_id, api=self.account_owner_api
        )

        self.lg("2- try to create machine with new user [user], should return 403")
        try:
            self.cloudapi_create_machine(
                cloudspace_id=self.cloudspace_id, api=self.user_api
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg(
            "3- try to clone created machine with new user [user], should return 403"
        )
        name = str(uuid.uuid4()).replace("-", "")[0:10]
        try:
            self.user_api.cloudapi.machines.clone(machineId=owner_machine_id, name=name)

        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg(
            "4- try to delete created machine with new user [user], should return 403"
        )
        try:
            self.user_api.cloudapi.machines.delete(
                machineId=owner_machine_id, permanently=True
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        self.lg("5- add user to the cloudspace created by user1 with write access")
        self.add_user_to_cloudspace(
            cloudspace_id=self.cloudspace_id, user=self.user, accesstype="CRX"
        )

        self.lg("6- create machine with new user [user], should succeed")
        machine_id = self.cloudapi_create_machine(
            cloudspace_id=self.cloudspace_id, api=self.user_api
        )

        self.lg("7- clone created machine with new user [user], should succeed")
        self.api.cloudapi.machines.stop(machineId=owner_machine_id)
        self.wait_for_status(
            "HALTED", self.api.cloudapi.machines.get, machineId=owner_machine_id
        )
        owner_machine = self.api.cloudapi.machines.get(machineId=owner_machine_id)
        self.assertEqual(owner_machine["status"], "HALTED")
        cloned_machine_id = self.user_api.cloudapi.machines.clone(
            machineId=owner_machine_id, name=name
        )
        self.wait_for_status(
            "RUNNING", self.api.cloudapi.machines.get, machineId=cloned_machine_id
        )
        cloned_machine = self.api.cloudapi.machines.get(machineId=cloned_machine_id)
        self.assertEqual(cloned_machine["status"], "RUNNING")

        self.lg("8- delete created machine with new user [user], should succeed")
        sleep(10)
        self.user_api.cloudapi.machines.delete(
            machineId=cloned_machine_id, permanently=True
        )
        sleep(10)
        try:
            self.api.cloudapi.machines.get(machineId=cloned_machine_id)
        except (HTTPError, ApiError) as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.status_code, 404)

        self.lg("%s ENDED" % self._testID)

    #     def test011_machine_importToNewMachine(self):
    #         pass
    #     def test012_machine_importToNewMachine_wrong(self):
    #         pass

    def test023_machine_addUser(self):
        """ ACL-22
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Checking if user2 has a write access on the created machine, should return 'CRX'

        """
        machine = self._machine_addUser_scenario_base()
        self.lg(
            "5- Checking if user2 has a write access on the created machine, should return CRX"
        )
        self.assertEqual(
            filter(lambda e: e["userGroupId"] == self.user2, machine["acl"])[0][
                "right"
            ],
            "CRX",
        )

    def test024_machine_addUser_wrong(self):
        """ ACL-23
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Adding non registered user to the created machine, should return 404 Not Found

        """
        machine = self._machine_addUser_scenario_base()
        self.not_user = str(uuid.uuid4()).replace("-", "")[0:10]  # non registered user
        self.lg(
            "5- Adding non registered user to the created machine, should return 404 Not Found"
        )
        try:
            self.user_api.cloudapi.machines.addUser(
                machineId=machine["id"], userId=self.not_user, accesstype="CRX"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")
        # to do .. should check if you pass wrong access type.

    def test025_machine_deleteUser(self):
        """ ACL-24
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Revoking user2 access to the created machine, should return empty list

        """
        machine = self._machine_addUser_scenario_base()
        self.lg(
            "5- Revoking user2 access to the created machine, should return empty list"
        )
        self.user_api.cloudapi.machines.deleteUser(
            machineId=machine["id"], userId=self.user2
        )
        machine_after_deleteuser = self.api.cloudapi.machines.get(machine["id"])
        self.assertEqual(
            filter(
                lambda e: e["userGroupId"] == self.user2,
                machine_after_deleteuser["acl"],
            ),
            [],
        )

    def test026_machine_deleteUser_wrong(self):
        """ ACL-25
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Deleting non registered user from the created machine

        """
        machine = self._machine_addUser_scenario_base()
        self.not_user = str(uuid.uuid4()).replace("-", "")[0:10]  # non registered user
        self.lg(
            "5- Deleting non registered user from the created machine, "
            "should return same machine acl before and after deleting"
        )
        try:
            self.user_api.cloudapi.machines.deleteUser(
                machineId=machine["id"], userId=self.not_user
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        machine_after_deleteuser = self.api.cloudapi.machines.get(machine["id"])
        self.assertEqual(machine_after_deleteuser["acl"], machine["acl"])

    def test027_machine_updateUser(self):
        """ ACL-26
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Giving user2 admin access to the created machine, should return ACDRUX

        """
        machine = self._machine_addUser_scenario_base()
        self.lg(
            "5- Giving user2 admin access to the created machine, should return ACDRUX"
        )
        self.user_api.cloudapi.machines.updateUser(
            machineId=machine["id"], userId=self.user2, accesstype="ACDRUX"
        )
        machine_after_updateuser = self.api.cloudapi.machines.get(machine["id"])
        self.assertEqual(
            filter(
                lambda e: e["userGroupId"] == self.user2,
                machine_after_updateuser["acl"],
            )[0]["right"],
            "ACDRUX",
        )

    def test028_machine_updateUser_wrong(self):
        """ ACL-27
        *Test case for to check cloud space user APIs with write access.*

        **Test Scenario:**

        #. Creating machine to the default cloud space created by the account_owner
        #. Giving the user write access on account_owner's cloud space
        #. Creating user2
        #. The user gives user2 write access to the newly created machine
        #. Adding user2 with wrong access to the created machine, should return 400 Bad Request
        #. Giving user2 read access to the created machine, should return 412
        #. Giving user2 write access to the created machine, should return 412
        #. Giving user2 wrong access to the newly created machine, should return 400 Bad Request
        #. Updating non_registered_user's access type, should return 404 Not Found
        #. Updating registered_user's access type who is not added to the machine, should return 404 Not Found

        """
        machine = self._machine_addUser_scenario_base()

        self.lg(
            "5- Adding user2 with wrong access to the created machine, should return 400 Bad Request"
        )
        try:
            self.user_api.cloudapi.machines.addUser(
                machineId=machine["id"], userId=self.user2, accesstype="ZYT"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "400 Bad Request")

        self.lg(
            "6- Giving user2 read access to the created machine, should return 412 "
        )
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=machine["id"], userId=self.user2, accesstype="R"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "412 Precondition Failed")

        self.lg(
            "7- Giving user2 write access to the created machine, should return 412 "
        )
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=machine["id"], userId=self.user2, accesstype="CRX"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "412 Precondition Failed")

        self.lg(
            "8- Giving user2 wrong access to the newly created machine, should return 400 Bad Request"
        )
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=machine["id"], userId=self.user2, accesstype="ZYT"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "400 Bad Request")

        self.not_user = str(uuid.uuid4()).replace("-", "")[0:10]  # non registered user
        self.lg(
            "9- Updating non_registered_user's access type, should return 404 Not Found"
        )
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=machine["id"], userId=self.not_user, accesstype="R"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg(
            "10- Updating registered_user's access type who is not added to the machine,"
            " should return 404 Not Found "
        )
        self.reg_user = self.cloudbroker_user_create()
        self.reg_user_api = self.get_authenticated_user_api(self.reg_user)
        try:
            self.user_api.cloudapi.machines.updateUser(
                machineId=machine["id"], userId=self.reg_user, accesstype="R"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        machine_after_updateuser = self.api.cloudapi.machines.get(machine["id"])
        self.assertEqual(machine_after_updateuser["acl"], machine["acl"])

    def test007_resize_machine(self):
        """ ACL-54
        *Test case for testing resize operation*

        **Test Scenario:**

        #. Creating machine to the account_owner
        #. Give the user write access to the cloudspace
        #. New user stop the machine
        #. Resize the machine with new user
        #. New user start the machine
        #. Check that the machine is updated
        """

        self.lg("1- Creating machine to the account_owner default cloud space")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("2- Give the user write access to the cloud space")
        self.account_owner_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.cloudspace_id, userId=self.user, accesstype="CRX"
        )

        self.lg("3- New user stop the machine")
        self.user_api.cloudapi.machines.stop(machineId=machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_id)["status"], "HALTED"
        )
        sleep(2)

        self.lg("4- Resize the machine with new user [user], should succeed")
        sizes = self.api.cloudapi.sizes.list(cloudspaceId=self.cloudspace_id)
        sizes = [size for size in sizes if size["id"] in range(1, 7)]
        resizeId = random.choice(sizes)["id"]
        self.lg("resize with size ID  %s" % resizeId)
        self.account_owner_api.cloudapi.machines.resize(
            machineId=machine_id, sizeId=resizeId
        )

        self.lg("5- New user start the machine")
        self.user_api.cloudapi.machines.start(machineId=machine_id)
        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_id)["status"], "RUNNING"
        )

        self.assertEqual(
            self.api.cloudapi.machines.get(machineId=machine_id)["sizeid"], resizeId
        )

        self.lg("%s ENDED" % self._testID)


class Admin(ACLCLOUDSPACE):
    def test003_cloudspace_add_update_delete_User(self):
        """ ACL-21
        *Test case for add/update/delete user api with user has admin access on cloud space level.*

        **Test Scenario:**

        #. add user2 to the cloudspace created by user1 as admin
        #. get cloudspace with user2
        #. create account for user3
        #. add user3 to the cloudspace by user2 with read access, should succeed
        #. update user3 access on cloudspace by user2 with write access, should succeed
        #. delete cloudspace user2 with user1, should succeed
        #. try to get cloudspace with user2, should fail '403 Forbidden'
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- add user2 to the cloudspace created by user1 as admin")
        self.api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.cloudspace_id, userId=self.user, accesstype="ACDRUX"
        )

        cloudspace = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)
        self.assertIn(self.user, [acl["userGroupId"] for acl in cloudspace["acl"]])
        acl_user = [
            acl for acl in cloudspace["acl"] if acl["userGroupId"] == self.user
        ][0]
        self.assertEqual(acl_user["right"], "ACDRUX")

        self.lg("2- get cloudspace with user2")
        cloudspace = self.user_api.cloudapi.cloudspaces.get(
            cloudspaceId=self.cloudspace_id
        )
        self.assertEqual(cloudspace["id"], self.cloudspace_id)

        self.lg("3- create account for user3")
        user3 = self.cloudbroker_user_create()

        self.lg("4- add user3 to the cloudspace by user2 with read access")
        self.user_api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.cloudspace_id, userId=user3, accesstype="R"
        )
        cloudspace = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)
        self.assertIn(user3, [acl["userGroupId"] for acl in cloudspace["acl"]])
        acl_user3 = [acl for acl in cloudspace["acl"] if acl["userGroupId"] == user3][0]
        self.assertEqual(acl_user3["right"], "R")

        self.lg("5- update user3 access on cloudspace by user2 with write access")
        self.user_api.cloudapi.cloudspaces.updateUser(
            cloudspaceId=self.cloudspace_id, userId=user3, accesstype="RCX"
        )
        cloudspace = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)
        acl_user3 = [acl for acl in cloudspace["acl"] if acl["userGroupId"] == user3][0]
        self.assertEqual(acl_user3["right"], "CRX")

        self.lg("6- delete cloudspace user: %s with user1" % self.user)
        self.user_api.cloudapi.cloudspaces.deleteUser(
            cloudspaceId=self.cloudspace_id, userId=self.user
        )

        self.lg("7- try to get cloudspace with user2")
        try:
            self.user_api.cloudapi.cloudspaces.get(cloudspaceId=self.cloudspace_id)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "403 Forbidden")

        cloudspace = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)
        self.assertEqual(cloudspace["id"], self.cloudspace_id)

        self.lg("%s ENDED" % self._testID)

    def test004_cloudspace_add_update_delete_User_wrong(self):
        """ ACL-28
        *Test case for add/update/delete user api wrong with user has admin access on cloud space level.*

        **Test Scenario:**

        #. add user2 to the cloudspace created by user1 as admin
        #. create user3
        #. use username not_registered_user which not exists
        #. try add not_registered_user to the cloudspace by admin user with read access, should return 404
        #. try update not_registered_user access on cloudspace by admin user with write access, should return 404
        #. try update user3 access on cloudspace by admin user with write access, should return 404
        #. try delete cloudspace not_registered_user with admin user, should return 404
        #. try to delete user3 from the cloudspace using admin user api, should return 404
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("1- add user2 to the cloudspace created by user1 as admin")
        self.api.cloudapi.cloudspaces.addUser(
            cloudspaceId=self.cloudspace_id, userId=self.user, accesstype="ACDRUX"
        )

        cloudspace = self.api.cloudapi.cloudspaces.get(self.cloudspace_id)
        self.assertIn(self.user, [acl["userGroupId"] for acl in cloudspace["acl"]])
        acl_user = [
            acl for acl in cloudspace["acl"] if acl["userGroupId"] == self.user
        ][0]
        self.assertEqual(acl_user["right"], "ACDRUX")

        self.lg("2- create user3")
        user3 = self.cloudbroker_user_create()

        self.lg("3- use username not_registered_user which not exists")
        not_registered_user = str(uuid.uuid4()).replace("-", "")[
            0:10
        ]  # non registered user

        self.lg(
            "4- try add not_registered_user to the cloudspace by admin user with read access"
        )
        try:
            self.user_api.cloudapi.cloudspaces.addUser(
                cloudspaceId=self.cloudspace_id,
                userId=not_registered_user,
                accesstype="R",
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg(
            "5- try update not_registered_user access on cloudspace by admin user with write access"
        )
        try:
            self.user_api.cloudapi.cloudspaces.updateUser(
                cloudspaceId=self.cloudspace_id,
                userId=not_registered_user,
                accesstype="RCX",
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg(
            "6- try update user3 access on cloudspace by admin user with write access"
        )
        try:
            self.user_api.cloudapi.cloudspaces.updateUser(
                cloudspaceId=self.cloudspace_id, userId=user3, accesstype="RCX"
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("7- try delete cloudspace not_registered_user with admin user")
        try:
            self.user_api.cloudapi.cloudspaces.deleteUser(
                cloudspaceId=self.cloudspace_id, userId=not_registered_user
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("8- try to delete user3 from the cloudspace using admin user api")
        try:
            self.user_api.cloudapi.cloudspaces.deleteUser(
                cloudspaceId=self.cloudspace_id, userId=user3
            )
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("%s ENDED" % self._testID)

    @unittest.skip("https://github.com/0-complexity/openvcloud/issues/1389")
    def test005_cloudspace_update_delete(self):
        """ ACL-29
        *Test case for update/delete cloudspace api with user has admin access.*

        **Test Scenario:**

        #. create new cloudspace and deploy machine
        #. add user2 to the cloudspace created by user1 as admin
        #. update cloudspace name, should succeed
        #. get and verify cloudspace with new name, should succeed
        #. update cloudspace max memory capacity, should succeed
        #. get and verify cloudspace memory, should succeed
        #. update cloudspace max disk capacity, should succeed
        #. get and verify cloudspace disk capacity, should succeed
        #. delete cloudspace, should succeed
        #. try to get deleted cloudspace, should fail '404 Not Found'
        """
        self.lg("%s STARTED" % self._testID)

        self.lg(
            "1- create new cloudspace and deploy machine with 4G memory and 10G disksize"
        )
        newcloudspaceId = self.cloudapi_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.account_owner,
            api=self.account_owner_api,
            maxMemoryCapacity=5,
            maxDiskCapacity=10,
        )
        self._cloudspaces = [newcloudspaceId]

        machine_id = self.cloudapi_create_machine(
            cloudspace_id=newcloudspaceId, api=self.account_owner_api, size_id=3
        )
        self.wait_for_status(
            "DEPLOYED",
            self.account_owner_api.cloudapi.cloudspaces.get,
            cloudspaceId=newcloudspaceId,
        )

        self.lg("2- add user2 to the cloudspace created by user1 as admin")
        self.api.cloudapi.cloudspaces.addUser(
            cloudspaceId=newcloudspaceId, userId=self.user, accesstype="ACDRUX"
        )

        cloudspace = self.user_api.cloudapi.cloudspaces.list()[0]
        self.assertIn(self.user, [acl["userGroupId"] for acl in cloudspace["acl"]])
        acl_user = [
            acl for acl in cloudspace["acl"] if acl["userGroupId"] == self.user
        ][0]
        self.assertEqual(acl_user["right"], "ACDRUX")

        self.lg("3- update cloudspace name")
        new_cloudspace_name = str(uuid.uuid4()).replace("-", "")[0:10]
        self.user_api.cloudapi.cloudspaces.update(
            cloudspaceId=newcloudspaceId, name=new_cloudspace_name
        )

        self.lg("- get and verify cloudspace with new name")
        scl = j.clients.osis.getNamespace("cloudbroker")
        cloudspace = scl.cloudspace.get(newcloudspaceId)
        self.assertEqual(cloudspace.name, new_cloudspace_name)

        self.lg("4- update cloudspace max memory capacity, should succeed")
        maxMemoryCapacity = 10
        self.user_api.cloudapi.cloudspaces.update(
            cloudspaceId=newcloudspaceId, maxMemoryCapacity=maxMemoryCapacity
        )

        self.lg("- get and verify cloudspace memory")
        cloudspace = scl.cloudspace.get(newcloudspaceId)
        self.assertEqual(cloudspace.resourceLimits["CU_M"], maxMemoryCapacity)

        self.lg("5- update cloudspace max disk capacity, should succeed")
        maxDiskCapacity = 20
        self.user_api.cloudapi.cloudspaces.update(
            cloudspaceId=newcloudspaceId, maxVDiskCapacity=maxDiskCapacity
        )

        self.lg("- get and verify cloudspace disk capacity")
        cloudspace = scl.cloudspace.get(newcloudspaceId)
        self.assertEqual(cloudspace.resourceLimits["CU_D"], maxDiskCapacity)

        self.lg("6- delete cloudspace.")
        self.account_owner_api.cloudapi.machines.delete(
            machineId=machine_id, permanently=True
        )
        self.user_api.cloudapi.cloudspaces.delete(
            cloudspaceId=newcloudspaceId, permanently=True
        )

        self.lg("7- try to get deleted cloudspace.")
        try:
            scl.cloudspace.get(newcloudspaceId)
        except ApiError as e:
            self.lg("- expected error raised %s" % e.message)
            self.assertEqual(e.message, "404 Not Found")

        self.lg("%s ENDED" % self._testID)
