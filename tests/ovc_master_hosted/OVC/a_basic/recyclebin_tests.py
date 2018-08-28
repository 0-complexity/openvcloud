from JumpScale import j
import unittest
import uuid
import random
import time
from ....utils.utils import BasicACLTest, VMClient
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError


class RecycleBinTests(BasicACLTest):
    def setUp(self):
        super(RecycleBinTests, self).setUp()
        self.acl_setup()
        self.models = j.clients.osis.getNamespace("cloudbroker")

    @parameterized.expand(["no", "yes"])
    def test001_delete_cloudbroker_empty_cloudspace(self, perma):
        """ OVC-001
        *Test case for deleting empty Cloud Space using cloudbroker API *

        **Test Scenario:**

        #. deleting empty cloudpsace using cloudbroker api, should succeed
        #. permanently deleting empty cloudpsace using cloudbroker api, should succeed
        #. creating cloudspace with same name as deleted cloudspace, should fail
        """
        self.lg("%s STARTED" % self._testID)
        if perma == "yes":
            permanently = True
            msg = "- permanently deleting empty cloudpsace using cloudbroker api, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting empty cloudpsace using cloudbroker api, should succeed"
            state = "DELETED"

        self.lg(msg)
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=self.cloudspace_id
        )
        if perma == "no":
            self.lg(
                "- creating cloudspace with same name as deleted cloudspace, should fail"
            )
            cloudspace_name = self.api.cloudapi.cloudspaces.get(
                cloudspaceId=self.cloudspace_id
            )["name"]
            with self.assertRaises(ApiError) as e:
                self.cloudapi_cloudspace_create(
                    account_id=self.account_id,
                    location=self.location,
                    access=self.account_owner,
                    api=self.account_owner_api,
                    wait=False,
                    name=cloudspace_name,
                )
                self.assertEqual(e.message, "409 Conflict")

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test002_delete_cloudapi_empty_cloudspace(self, perma):
        """ OVC-002
        *Test case for deleting empty Cloud Space using cloudapi API *

        **Test Scenario:**

        #. deleting empty cloudpsace using cloudapi api, should succeed
        #. permanently deleting empty cloudpsace using cloudapi api, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting empty cloudpsace using cloudapi api, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting empty cloudpsace using cloudapi api, should succeed"
            state = "DELETED"

        self.lg(msg)
        self.api.cloudapi.cloudspaces.delete(
            cloudspaceId=self.cloudspace_id, permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=self.cloudspace_id
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test003_delete_cloudbroker_cloudspace(self, perma):
        """ OVC-003
        *Test case for deleting Cloud Space with machine using cloudbroker API *

        **Test Scenario:**

        #. creating machine under current cloudspace, should succeed
        #. deleting cloudpsace with machine using cloudbroker api, should succeed
        #. permanently deleting cloudpsace with machine using cloudbroker api, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting cloudpsace with machine using cloudbroker api, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting cloudpsace with machine using cloudbroker api, should succeed"
            state = "DELETED"

        self.lg("- creating machine under current cloudspace, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg(msg)
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=self.cloudspace_id
        )

        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.get(machineId=machine_id)
        self.assertEqual(e.exception.status_code, 404)

        machine_status = self.models.vmachine.get(machine_id).status
        self.assertEqual(machine_status, state)
        self.lg("%s ENDED" % self._testID)

    def test004_delete_cloudapi_cloudspace_with_running_machine(self):
        """ OVC-004
        *Test case for deleting Cloud Space with running machine using cloudapi API *

        **Test Scenario:**

        #. creating machine under current cloudspace, should succeed
        #. deleting cloudpsace with running machine using cloudapi api, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating machine under current cloudspace, should succeed")
        self.cloudapi_create_machine(self.cloudspace_id, self.account_owner_api)

        self.lg(
            "- deleting cloudpsace with running machine using cloudapi api, should fail"
        )
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.delete(
                cloudspaceId=self.cloudspace_id, permanently=False
            )
        self.assertEqual(e.exception.status_code, 409)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test005_delete_cloudapi_cloudspace(self, perma):
        """ OVC-005
        *Test case for deleting Cloud Space with deleted machine using cloudapi API *

        **Test Scenario:**

        #. creating machine under current cloudspace, should succeed
        #. deleting created machine, should succeed
        #. deleting cloudpsace with machine using cloudapi api, should succeed
        #. permanently deleting cloudpsace with machine using cloudapi api, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting cloudpsace with machine using cloudapi api, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = (
                "- deleting cloudpsace with machine using cloudapi api, should succeed"
            )
            state = "DELETED"

        self.lg("- creating machine under current cloudspace, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- deleting created machine, should succeed")
        self.api.cloudapi.machines.delete(machine_id)

        self.lg(msg)
        self.api.cloudapi.cloudspaces.delete(
            cloudspaceId=self.cloudspace_id, permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=self.cloudspace_id
        )

        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.get(machineId=machine_id)
        self.assertEqual(e.exception.status_code, 404)

        machine_status = self.models.vmachine.get(machine_id).status
        self.assertEqual(machine_status, state)
        self.lg("%s ENDED" % self._testID)

    def test006_delete_cloudspace_deploying(self):
        """ OVC-006
        *Test case for deleting Cloud Space that is still being deployed *

        **Test Scenario:**

        #. creating cloudspace, should succeed
        #. deleting deploying cloudspace, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating cloudspace, should succeed")
        cloudspace_id = self.cloudapi_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.account_owner,
            api=self.account_owner_api,
            wait=False,
        )

        self.lg(" deleting deploying cloudspace, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.delete(cloudspaceId=cloudspace_id)
        self.assertEqual(e.exception.status_code, 400)

        self.wait_for_status(
            "DEPLOYED", self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspace_id
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["cloudbroker", "cloudapi"])
    def test007_perma_destroy_deleted_cloudspace(self, api):
        """ OVC-007
        *Test case for destroying deleted Cloud Space *

        **Test Scenario:**

        #. deleting cloudspace, should succeed
        #. permanently destroying deleted cloudspace using cloudbroker, should succeed
        #. permanently destroying deleted cloudspace using cloudapi, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- deleting cloudspace, should succeed")
        self.api.cloudapi.cloudspaces.delete(cloudspaceId=self.cloudspace_id)
        self.wait_for_status(
            "DELETED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        msg = "- permanently destroying deleted cloudspace using %s, should succeed"

        if api == "cloudbroker":
            self.lg(msg % api)
            self.api.cloudbroker.cloudspace.destroy(
                cloudspaceId=self.cloudspace_id, reason="Test case", permanently=True
            )
        else:
            self.lg(msg % api)
            self.api.cloudapi.cloudspaces.delete(
                cloudspaceId=self.cloudspace_id, permanently=True
            )

        self.wait_for_status(
            "DESTROYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["cloudbroker", "cloudapi"])
    def test008_delete_destroyed_cloudspace(self, api):
        """ OVC-008
        *Test case for deleting/destroying destroyed cloudspace *

        **Test Scenario:**

        #. destroying cloudspace, should succeed
        #. deleting destroyed cloudspace using cloudbroker, should succeed
        #. destroying destroyed cloudspace using cloudbroker, should succeed
        #. deleting destroyed cloudspace using cloudapi, should succeed
        #. destroying destroyed cloudspace using cloudapi, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- destroying cloudspace, should succeed")
        self.api.cloudapi.cloudspaces.delete(
            cloudspaceId=self.cloudspace_id, permanently=True
        )

        self.wait_for_status(
            "DESTROYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        delete_msg = "- deleting destroyed cloudspace using %s, should succeed"
        destroy_msg = "- destroying destroyed cloudspace using %s, should succeed"

        if api == "cloudbroker":
            self.lg(delete_msg % api)
            self.api.cloudbroker.cloudspace.destroy(
                cloudspaceId=self.cloudspace_id, reason="Test case"
            )
            self.lg(destroy_msg % api)
            self.api.cloudbroker.cloudspace.destroy(
                cloudspaceId=self.cloudspace_id, reason="Test case", permanently=True
            )
        else:
            self.lg(delete_msg % api)
            self.api.cloudapi.cloudspaces.delete(cloudspaceId=self.cloudspace_id)
            self.lg(destroy_msg % api)
            self.api.cloudapi.cloudspaces.delete(
                cloudspaceId=self.cloudspace_id, permanently=True
            )

        self.lg("%s ENDED" % self._testID)

    def test009_restore_deleted_cloudspace(self):
        """ OVC-009
        *Test case for restoring deleted cloudspace *

        **Test Scenario:**

        #. creating machine under current cloudspace, should succeed
        #. deleting cloudspace, should succeed
        #. restoring cloudspace, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating machine under current cloudspace, should succeed")
        self.cloudapi_create_machine(self.cloudspace_id, self.account_owner_api)

        self.lg("- deleting cloudspace, should succeed")
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("- restoring cloudspace, should succeed")
        self.api.cloudapi.cloudspaces.restore(
            cloudspaceId=self.cloudspace_id, reason="Test case"
        )

        self.wait_for_status(
            "DEPLOYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("%s ENDED" % self._testID)

    def test010_restore_not_deleted_cloudspace(self):
        """ OVC-010
        *Test case for restoring non deleted cloudspace *

        **Test Scenario:**

        #. restoring cloudspace, should fail
        #. destroying cloudspace, should succeed
        #. restoring destroyed cloudspace, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- restoring cloudspace, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.restore(
                cloudspaceId=self.cloudspace_id, reason="Test case"
            )
        self.assertEqual(e.exception.status_code, 400)

        self.lg("- destroying cloudspace, should succeed")
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id, reason="Test case", permanently=True
        )

        self.wait_for_status(
            "DESTROYED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("- restoring destroyed cloudspace, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.restore(
                cloudspaceId=self.cloudspace_id, reason="Test case"
            )
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    def test011_restore_cloudspace_account_deleted(self):
        """ OVC-011
        *Test case for restoring cloudspace on a deleted account *

        **Test Scenario:**

        #. deleting account, should succeed
        #. restoring cloudspace, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- deleting account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- restoring cloudspace, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.cloudspaces.restore(
                cloudspaceId=self.cloudspace_id, reason="Test case"
            )
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test012_delete_cloudspaces(self, perma):
        """ OVC-012
        *Test case for deleting multiple cloudspaces *

        **Test Scenario:**

        #. creating cloudspace, should succeed
        #. destroying Cloud Spaces, should succeed
        #. deleting Cloud Spaces, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating cloudspace, should succeed")
        cloudspace_id1 = self.cloudapi_cloudspace_create(
            account_id=self.account_id,
            location=self.location,
            access=self.account_owner,
            api=self.account_owner_api,
        )
        if perma == "yes":
            permanently = True
            msg = "- destroying Cloud Spaces, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting Cloud Spaces, should succeed"
            state = "DELETED"

        self.lg(msg)
        ids = [self.cloudspace_id, cloudspace_id1]
        self.api.cloudbroker.cloudspace.destroyCloudSpaces(
            cloudspaceIds=ids, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=self.cloudspace_id
        )
        self.wait_for_status(
            state, self.api.cloudapi.cloudspaces.get, cloudspaceId=cloudspace_id1
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test013_delete_account(self, perma):
        """ OVC-013
        *Test case for deleting Account *

        **Test Scenario:**

        #. deleting account, should succeed
        #. permanently deleting account, should succeed
        #. creating account with same name as deleted account, should fail
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting account, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting account, should succeed"
            state = "DELETED"

        self.lg(msg)
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        if perma == "no":
            self.lg("- creating account with same name as deleted account, should fail")
            account_name = self.api.cloudapi.accounts.get(accountId=self.account_id)[
                "name"
            ]
            with self.assertRaises(HTTPError) as e:
                self.cloudbroker_account_create(
                    account_name, self.account_owner, self.email
                )
            self.assertEqual(e.exception.status_code, 409)

        cloudspace_status = self.api.cloudapi.cloudspaces.get(
            cloudspaceId=self.cloudspace_id
        )["status"]
        self.assertEqual(cloudspace_status, state)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test014_delete_account_with_image(self, perma):
        """ OVC-014
        *Test case for deleting Account with an image as well as a machine *

        **Test Scenario:**

        #. creating image in current account, should succeed
        #. creating machine in current account using new image, should succeed
        #. deleting account, should succeed
        #. permanently deleting account, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image in current account, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- creating machine in current account using new image, should succeed")
        self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api, image_id=image_id
        )

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting account, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting account, should succeed"
            state = "DELETED"

        self.lg(msg)
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("%s ENDED" % self._testID)

    def test015_perma_destroy_deleted_account(self):
        """ OVC-015
        *Test case for destroying deleted Account *

        **Test Scenario:**

        #. deleting account, should succeed
        #. permanently destroying deleted account, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- deleting account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )
        self.wait_for_status(
            "DELETED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- permanently destroying deleted account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=True
        )

        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("%s ENDED" % self._testID)

    def test016_delete_destroyed_account(self):
        """ OVC-016
        *Test case for deleting/destroying destroyed account *

        **Test Scenario:**

        #. destroying account, should succeed
        #. deleting destroyed account, should succeed
        #. destroying destroyed account, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- destroying account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=True
        )

        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("deleting destroyed account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )
        self.lg("destroying destroyed account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=True
        )

        self.lg("%s ENDED" % self._testID)

    def test017_restore_deleted_account(self):
        """ OVC-0017
        *Test case for restoring deleted account *

        **Test Scenario:**

        #. creating image on account, should succeed
        #. deleting account, should succeed
        #. restoring account, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image on account, should succeed")
        self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- deleting account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- restoring account, should succeed")
        self.api.cloudbroker.account.restore(
            accountId=self.account_id, reason="Test case"
        )

        self.wait_for_status(
            "CONFIRMED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("%s ENDED" % self._testID)

    def test018_restore_not_deleted_account(self):
        """ OVC-018
        *Test case for restoring non deleted account *

        **Test Scenario:**

        #. restoring account, should fail
        #. destroying account, should succeed
        #. restoring destroyed account, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- restoring account, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.account.restore(
                accountId=self.account_id, reason="Test case"
            )
        self.assertEqual(e.exception.status_code, 400)

        self.lg("- destroying account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=True
        )

        self.wait_for_status(
            "DESTROYED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- restoring destroyed account, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.account.restore(
                accountId=self.account_id, reason="Test case"
            )
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test019_delete_accounts(self, perma):
        """ OVC-019
        *Test case for deleting multiple accounts *

        **Test Scenario:**

        #. creating Account, should succeed
        #. destroying Accounts, should succeed
        #. deleting Accounts, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Account, should succeed")
        account_id1 = self.cloudbroker_account_create(
            str(uuid.uuid4()).replace("-", "")[0:10], self.account_owner, self.email
        )
        if perma == "yes":
            permanently = True
            msg = "- destroying Accounts, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting Accounts, should succeed"
            state = "DELETED"

        self.lg(msg)
        ids = [self.account_id, account_id1]
        self.api.cloudbroker.account.deleteAccounts(
            accountIds=ids, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.accounts.get, accountId=self.account_id
        )
        self.wait_for_status(
            state, self.api.cloudapi.accounts.get, accountId=account_id1
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test020_delete_machine(self, perma):
        """ OVC-020
        *Test case for deleting Virtual Machine *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. deleting Virtual Machine, should succeed
        #. permanently deleting Virtual Machine, should succeed
        #. creating machine with same name as deleted machine, should fail
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting Virtual Machine, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting Virtual Machine, should succeed"
            state = "DELETED"

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg(msg)
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=permanently)

        self.wait_for_status(
            state, self.models.vmachine.searchOne, query={"id": machine_id}
        )

        if perma == "no":
            self.lg("- creating machine with same name as deleted machine, should fail")
            machine_name = self.models.vmachine.searchOne({"id": machine_id})["name"]
            with self.assertRaises(ApiError) as e:
                self.cloudapi_create_machine(
                    self.cloudspace_id, self.account_owner_api, machine_name
                )
                self.assertEqual(e.message, "409 Conflict")

        self.lg("%s ENDED" % self._testID)

    def test021_perma_destroy_deleted_machine(self):
        """ OVC-021
        *Test case for destroying deleted Virtual Machine *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. deleting Virtual Machine, should succeed
        #. permanently destroying Virtual Machine, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- deleting Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=False)
        self.wait_for_status(
            "DELETED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("- permanently destroying Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("%s ENDED" % self._testID)

    def test022_delete_machine_with_clone(self):
        """ OVC-022
        *Test case for deleting Virtual Machine with clone *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. stopping Virtual Machine for cloning, should succeed
        #. cloning Virtual Machine, should succeed
        #. deleting Virtual Machine, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- stopping Virtual Machine for cloning, should succeed")
        self.api.cloudapi.machines.stop(machineId=machine_id)

        self.lg("- cloning Virtual Machine, should succeed")
        clone_name = str(uuid.uuid4()).replace("-", "")[0:10]
        self.api.cloudapi.machines.clone(machineId=machine_id, name=clone_name)

        self.lg("- deleting Virtual Machine, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.delete(machineId=machine_id)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("%s ENDED" % self._testID)

    def test023_delete_destroyed_machine(self):
        """ OVC-023
        *Test case for deleting/destroying destroyed machine *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. destroying Virtual Machine, should succeed
        #. deleting destroyed Virtual Machine, should succeed
        #. destroying destroyed Virtual Machine, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- destroying Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("deleting destroyed Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id)
        self.lg("destroying destroyed Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=True)

        self.lg("%s ENDED" % self._testID)

    def test024_restore_deleted_machine(self):
        """ OVC-024
        *Test case for restoring deleted machine *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. deleting Virtual Machine, should succeed
        #. restoring Virtual Machine, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- deleting Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id)

        self.wait_for_status(
            "DELETED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("- restoring Virtual Machine, should succeed")
        self.api.cloudapi.machines.restore(machineId=machine_id, reason="Test case")

        self.wait_for_status(
            "HALTED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("%s ENDED" % self._testID)

    def test025_restore_not_deleted_machine(self):
        """ OVC-025
        *Test case for restoring non deleted machine *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. restoring Virtual Machine, should fail
        #. destroying Virtual Machine, should succeed
        #. restoring destroyed Virtual Machine, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- restoring Virtual Machine, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.restore(machineId=machine_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 400)

        self.lg("- destroying Virtual Machine, should succeed")
        self.api.cloudapi.machines.delete(machineId=machine_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.lg("- restoring destroyed Virtual Machine, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.restore(machineId=machine_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    def test026_restore_deleted_machine_cloudspace_deleted(self):
        """ OVC-026
        *Test case for restoring deleted machine on a deleted Cloud Space *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. deleting current Cloud Space, should succeed
        #. restoring Virtual Machine, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- deleting cloudspace, should succeed")
        self.api.cloudbroker.cloudspace.destroy(
            cloudspaceId=self.cloudspace_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED",
            self.api.cloudapi.cloudspaces.get,
            cloudspaceId=self.cloudspace_id,
        )

        self.lg("- restoring Virtual Machine, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.machines.restore(machineId=machine_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test027_delete_machines(self, perma):
        """ OVC-027
        *Test case for deleting multiple machines *

        **Test Scenario:**

        #. creating Virtual Machine, should succeed
        #. creating another Virtual Machine, should succeed
        #. destroying Virtual Machines, should succeed
        #. deleting Virtual Machines, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- creating another Virtual Machine, should succeed")
        machine_id1 = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        if perma == "yes":
            permanently = True
            msg = "- destroying Virtual Machines, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting Virtual Machines, should succeed"
            state = "DELETED"

        self.lg(msg)
        ids = [machine_id, machine_id1]
        self.api.cloudbroker.machine.destroyMachines(
            machineIds=ids, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.models.vmachine.searchOne, query={"id": machine_id}
        )
        self.wait_for_status(
            state, self.models.vmachine.searchOne, query={"id": machine_id1}
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test028_delete_image(self, perma):
        """ OVC-028
        *Test case for deleting image *

        **Test Scenario:**

        #. creating image, should succeed
        #. deleting image, should succeed
        #. permanently deleting image, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting image, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting image, should succeed"
            state = "DELETED"

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg(msg)
        self.api.cloudapi.images.delete(imageId=image_id, permanently=permanently)

        self.wait_for_status(state, self.models.image.searchOne, query={"id": image_id})

        self.lg("%s ENDED" % self._testID)

    def test029_perma_destroy_deleted_image(self):
        """ OVC-029
        *Test case for destroying deleted image *

        **Test Scenario:**

        #. creating image, should succeed
        #. deleting image, should succeed
        #. permanently destroying image, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- deleting image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id, permanently=False)
        self.wait_for_status(
            "DELETED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("- permanently destroying image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("%s ENDED" % self._testID)

    def test030_destroy_used_image(self):
        """ OVC-030
        *Test case for destroying image that is being used by a machine *

        **Test Scenario:**

        #. creating image, should succeed
        #. creating Virtual Machine with the image, should succeed
        #. deleting image, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- creating Virtual Machine with the image, should succeed")
        self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api, image_id=image_id
        )

        self.lg("- deleting image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.delete(imageId=image_id, permanently=True)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("%s ENDED" % self._testID)

    def test031_delete_system_image(self):
        """ OVC-031
        *Test case for deleting a system image(doesn't belong to an account) *

        **Test Scenario:**

        #. creating image without account, should succeed
        #. deleting image, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image without account, should succeed")
        image_id = self.cloudbroker_create_image()

        self.lg("- deleting image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.delete(imageId=image_id)
        self.assertEqual(e.exception.status_code, 405)

        self.lg("%s ENDED" % self._testID)

    def test032_delete_creating_image(self):
        """ OVC-032
        *Test case for deleting image that is still being created *

        **Test Scenario:**

        #. creating image, should succeed
        #. deleting image, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id, wait=False)

        self.lg("- deleting image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.delete(imageId=image_id)
        self.assertEqual(e.exception.status_code, 403)

        self.wait_for_status(
            "CREATED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("%s ENDED" % self._testID)

    def test033_delete_destroyed_image(self):
        """ OVC-033
        *Test case for deleting/destroying destroyed image *

        **Test Scenario:**

        #. creating image, should succeed
        #. destroying image, should succeed
        #. deleting destroyed image, should succeed
        #. destroying destroyed image, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- destroying image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("deleting destroyed image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id)
        self.lg("destroying destroyed image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id, permanently=True)

        self.lg("%s ENDED" % self._testID)

    def test034_restore_deleted_image(self):
        """ OVC-034
        *Test case for restoring deleted image *

        **Test Scenario:**

        #. creating image, should succeed
        #. deleting image, should succeed
        #. restoring image, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- deleting image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id)

        self.wait_for_status(
            "DELETED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("- restoring image, should succeed")
        self.api.cloudapi.images.restore(imageId=image_id)

        self.wait_for_status(
            "CREATED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("%s ENDED" % self._testID)

    def test035_restore_not_deleted_image(self):
        """ OVC-035
        *Test case for restoring non deleted image *

        **Test Scenario:**

        #. creating image, should succeed
        #. restoring image, should fail
        #. destroying image, should succeed
        #. restoring destroyed image, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- restoring image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.restore(imageId=image_id)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("- destroying image, should succeed")
        self.api.cloudapi.images.delete(imageId=image_id, permanently=True)

        self.wait_for_status(
            "DESTROYED", self.models.image.searchOne, query={"id": image_id}
        )

        self.lg("- restoring destroyed image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.restore(imageId=image_id)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    def test036_restore_deleted_image_account_deleted(self):
        """ OVC-0036
        *Test case for restoring deleted machine on a deleted Account *

        **Test Scenario:**

        #. creating image, should succeed
        #. deleting current account, should succeed
        #. restoring image, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- deleting current account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- restoring image, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.images.restore(imageId=image_id)
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test037_delete_images(self, perma):
        """ OVC-037
        *Test case for deleting multiple images *

        **Test Scenario:**

        #. creating image, should succeed
        #. creating another image, should succeed
        #. destroying images, should succeed
        #. deleting images, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating image, should succeed")
        image_id = self.cloudbroker_create_image(account_id=self.account_id)

        self.lg("- creating another image, should succeed")
        image_id1 = self.cloudbroker_create_image(account_id=self.account_id)

        if perma == "yes":
            permanently = True
            msg = "- destroying images, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting images, should succeed"
            state = "DELETED"

        self.lg(msg)
        ids = [image_id, image_id1]
        self.api.cloudbroker.image.deleteImages(
            imageIds=ids, reason="Test case", permanently=permanently
        )

        self.wait_for_status(state, self.models.image.searchOne, query={"id": image_id})
        self.wait_for_status(
            state, self.models.image.searchOne, query={"id": image_id1}
        )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test038_delete_cdrom(self, perma):
        """ OVC-038
        *Test case for deleting CD-ROM disk *

        **Test Scenario:**

        #. creating CD-ROM disk, should succeed
        #. deleting CD-ROM disk, should succeed
        #. permanently deleting CD-ROM disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting CD-ROM disk, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting CD-ROM disk, should succeed"
            state = "TOBEDELETED"

        self.lg("- creating CD-ROM disk, should succeed")
        disk_id = self.create_cdrom()

        self.lg(msg)
        self.api.cloudbroker.image.deleteCDROMImage(
            diskId=disk_id, permanently=permanently
        )

        self.wait_for_status(state, self.api.cloudapi.disks.get, diskId=disk_id)

        if perma == "no":
            self.api.cloudbroker.image.deleteCDROMImage(
                diskId=disk_id, permanently=True
            )
            self.wait_for_status(
                "DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id
            )

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test039_delete_disk(self, perma):
        """ OVC-039
        *Test case for deleting disk *

        **Test Scenario:**

        #. creating disk, should succeed
        #. deleting disk, should succeed
        #. permanently deleting disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting disk, should succeed"
            state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting disk, should succeed"
            state = "TOBEDELETED"

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg(msg)
        self.api.cloudapi.disks.delete(
            diskId=disk_id, detach=False, permanently=permanently
        )

        self.wait_for_status(state, self.api.cloudapi.disks.get, diskId=disk_id)
        if perma == "no":
            self.api.cloudapi.disks.delete(
                diskId=disk_id, detach=False, permanently=True
            )
            self.wait_for_status(
                "DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id
            )

        self.lg("%s ENDED" % self._testID)

    def test040_perma_destroy_deleted_disk(self):
        """ OVC-040
        *Test case for destroying deleted disk *

        **Test Scenario:**

        #. creating disk, should succeed
        #. deleting disk, should succeed
        #. permanently destroying disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- deleting disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=False)

        self.lg("- permanently destroying disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=True)

        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("%s ENDED" % self._testID)

    def test041_destroy_used_disk(self):
        """ OVC-041
        *Test case for destroying disk that is attached to a machine without detaching *

        **Test Scenario:**

        #. creating disk, should succeed
        #. creating Virtual Machine with the image, should succeed
        #. attaching created disk to the creted machine
        #. deleting disk, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- attaching created disk to the creted machine")
        self.api.cloudapi.machines.attachDisk(machineId=machine_id, diskId=disk_id)

        self.wait_for_status("ASSIGNED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("- deleting disk, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)
        self.assertEqual(e.exception.status_code, 409)

        self.lg("%s ENDED" % self._testID)

    def test042_destroy_used_disk_detach(self):
        """ OVC-042
        *Test case for destroying disk that is attached to a machine with detaching *

        **Test Scenario:**

        #. creating disk, should succeed
        #. creating Virtual Machine with the image, should succeed
        #. attaching created disk to the creted machine
        #. deleting disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- attaching created disk to the creted machine")
        self.api.cloudapi.machines.attachDisk(machineId=machine_id, diskId=disk_id)

        self.wait_for_status("ASSIGNED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("- deleting disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=True)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test043_destroy_used_cdrom_used(self, destroy_machine):
        """ OVC-043
        *Test case for destroying CD-ROM that is used by a machine *

        **Test Scenario:**

        #. creating CD-ROM, should succeed
        #. creating Virtual Machine with the image, should succeed
        #. stopping created machine
        #. starting created machine with created CD-ROM
        #. deleting CD-ROM, should fail
        #. destroying created machine to free created CD-ROM
        #. stopping created machine to stop using created CD-ROM
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating CD-ROM, should succeed")
        disk_id = self.create_cdrom()

        self.lg("- creating Virtual Machine, should succeed")
        machine_id = self.cloudapi_create_machine(
            self.cloudspace_id, self.account_owner_api
        )

        self.lg("- stopping created machine")
        self.api.cloudapi.machines.stop(machineId=machine_id)

        self.lg("- starting created machine with created CD-ROM")
        self.api.cloudapi.machines.start(machineId=machine_id, diskId=disk_id)

        self.lg("- deleting CD-ROM, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudbroker.image.deleteCDROMImage(diskId=disk_id)
        self.assertEqual(e.exception.status_code, 409)

        if destroy_machine == "yes":
            self.lg("- destroying created machine to free created CD-ROM")
            self.api.cloudapi.machines.delete(machineId=machine_id, permanently=True)
            state = "DESTROYED"
        else:
            self.lg("- stopping created machine to stop using created CD-ROM")
            self.api.cloudapi.machines.stop(machineId=machine_id)
            state = "HALTED"

        self.wait_for_status(
            state, self.models.vmachine.searchOne, query={"id": machine_id}
        )

        self.api.cloudbroker.image.deleteCDROMImage(diskId=disk_id, permanently=True)
        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("%s ENDED" % self._testID)

    def test044_delete_destroyed_disk(self):
        """ OVC-044
        *Test case for deleting/destroying destroyed disk *

        **Test Scenario:**

        #. creating disk, should succeed
        #. destroying disk, should succeed
        #. deleting destroyed disk, should succeed
        #. destroying destroyed disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- destroying disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=True)

        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("deleting destroyed disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)
        self.lg("destroying destroyed disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=True)

        self.lg("%s ENDED" % self._testID)

    def test045_restore_deleted_disk(self):
        """ OVC-045
        *Test case for restoring deleted disk *

        **Test Scenario:**

        #. creating disk, should succeed
        #. deleting disk, should succeed
        #. restoring disk, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- deleting disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False)

        self.wait_for_status("TOBEDELETED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("- restoring disk, should succeed")
        self.api.cloudapi.disks.restore(diskId=disk_id, reason="Test case")

        self.wait_for_status("CREATED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=True)
        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("%s ENDED" % self._testID)

    def test046_restore_not_deleted_disk(self):
        """ OVC-046
        *Test case for restoring non deleted image *

        **Test Scenario:**

        #. creating disk, should succeed
        #. restoring disk, should fail
        #. destroying disk, should succeed
        #. restoring destroyed disk, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- restoring disk, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.restore(diskId=disk_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 400)

        self.lg("- destroying disk, should succeed")
        self.api.cloudapi.disks.delete(diskId=disk_id, detach=False, permanently=True)

        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)

        self.lg("- restoring destroyed disk, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.restore(diskId=disk_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 404)

        self.lg("%s ENDED" % self._testID)

    def test047_delete_disks(self):
        """ OVC-047
        *Test case for deleting multiple disks *

        **Test Scenario:**

        #. creating disk, should succeed
        #. creating another disk, should succeed
        #. destroying disks, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- creating another disk, should succeed")
        disk_id1 = self.create_disk(self.account_id)

        self.lg("- destroying disks, should succeed")
        ids = [disk_id, disk_id1]
        self.api.cloudapi.disks.deleteDisks(diskIds=ids, reason="Test case")

        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id)
        self.wait_for_status("DESTROYED", self.api.cloudapi.disks.get, diskId=disk_id1)

        self.lg("%s ENDED" % self._testID)

    def test048_restore_deleted_disk_account_deleted(self):
        """ OVC-0048
        *Test case for restoring deleted disk on a deleted Account *

        **Test Scenario:**

        #. creating disk, should succeed
        #. deleting current account, should succeed
        #. restoring disk, should fail
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk, should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("- deleting current account, should succeed")
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case"
        )

        self.wait_for_status(
            "DELETED", self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        self.lg("- restoring disk, should fail")
        with self.assertRaises(HTTPError) as e:
            self.api.cloudapi.disks.restore(diskId=disk_id, reason="Test case")
        self.assertEqual(e.exception.status_code, 400)

        self.lg("%s ENDED" % self._testID)

    @parameterized.expand(["no", "yes"])
    def test049_delete_account_with_disk(self, perma):
        """ OVC-049
        *Test case for deleting Account with a disk *

        **Test Scenario:**

        #. creating disk in current account, should succeed
        #. deleting account, should succeed
        #. permanently deleting account, should succeed
        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating disk in current account, should succeed")
        disk_id = self.create_disk(self.account_id)

        if perma == "yes":
            permanently = True
            msg = "- permanently deleting account, should succeed"
            state = "DESTROYED"
            disk_state = "DESTROYED"
        else:
            permanently = False
            msg = "- deleting account, should succeed"
            state = "DELETED"
            disk_state = "TOBEDELETED"

        self.lg(msg)
        self.api.cloudbroker.account.delete(
            accountId=self.account_id, reason="Test case", permanently=permanently
        )

        self.wait_for_status(
            state, self.api.cloudapi.accounts.get, accountId=self.account_id
        )

        disk_status = self.api.cloudapi.disks.get(diskId=disk_id)["status"]
        self.assertEqual(disk_status, disk_state)

        self.lg("%s ENDED" % self._testID)
