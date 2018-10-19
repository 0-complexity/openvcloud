import unittest
import uuid
import random
import time
import gevent
from JumpScale import j
from ....utils.utils import BasicACLTest
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError

ccl = j.clients.osis.getNamespace("cloudbroker")
pcl = j.clients.portal.getByInstance("main")

class StatusTests(BasicACLTest):

    @unittest.skip("")
    def test001_create_multiple_cloudspace_with_same_name(self):
        """ StatusTestOVC-001
            *Test case for creating multiple Cloud Spaces with the same name*
            Only one Cloud Space should be created

        """        
        spaces_nr = 5
        name = "test space"
        self.default_setup(create_default_cloudspace=False)
        
        jobs = []
        for _ in xrange(spaces_nr):
            jobs.append(
                gevent.spawn(
                self.cloudapi_cloudspace_create,
                account_id=self.account_id,
                location=self.location,
                access=self.account_owner,
                api=self.account_owner_api,
                name="test space",
                )
            )

        gevent.joinall(jobs)
        created_spaces_nr = ccl.cloudspace.search({'name': name, 'status': {'$ne': "DESTROYED"}, 'accountId': self.account_id})[0]
        self.assertEqual(created_spaces_nr, 1)
        gevent.joinall(jobs)

    @unittest.skip("")
    def test001_disable_cloudspace_cloudapi(self):
        """ StatusesOVC-002
        *Test case for disabling Cloud Space using cloudapi API*

        **Test Scenario:**

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating machine under current cloudspace, should succeed")
        self.default_setup(create_default_cloudspace=True)

        self.api.cloudapi.cloudspaces.disable(self.cloudspace_id, reason='testing')

        status = ccl.cloudspace.searchOne({'id': self.cloudspace_id})['status']
        self.assertEqual(status, 'DISABLED')

        self.api.cloudapi.cloudspaces.enable(self.cloudspace_id, reason='testing')

        status = ccl.cloudspace.searchOne({'id': self.cloudspace_id})['status']
        self.assertEqual(status, 'DEPLOYED')

        self.lg("%s ENDED" % self._testID)

    # @unittest.skip("")
    def test001_stopVFW(self):
        """ StatusesOVC-003
        *Test case for stoping VFW*

        **Test Scenario:**

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating machine under current cloudspace, should succeed")
        self.default_setup(create_default_cloudspace=True)

        import ipdb; ipdb.set_trace()
        self.api.cloudapi.cloudbroker.disable(self.cloudspace_id, reason='testing')

        status = ccl.cloudspace.searchOne({'id': self.cloudspace_id})['status']
        self.assertEqual(status, 'DISABLED')

        self.api.cloudapi.cloudspaces.enable(self.cloudspace_id, reason='testing')

        self.assertEqual(self.get_cloudspace()['status'], 'DEPLOYED')

        self.lg("%s ENDED" % self._testID)

    @unittest.skip("")
    def test001_delete_vfw(self):
        """ StatusesOVC-003
        *Test case for disabling Cloud Space using cloudapi API*

        **Test Scenario:**

        """
        self.lg("%s STARTED" % self._testID)

        self.lg("- creating machine under current cloudspace, should succeed")
        self.default_setup(create_default_cloudspace=True)

        import ipdb; ipdb.set_trace()
        self.api.cloudapi.cloudspace.desable(self.cloudspace_id)
        
        self.assertEqual(self.get_cloudspace()['status'], 'DISABLED')

        self.api.cloudapi.cloudspace.enable(self.cloudspace_id)

        self.assertEqual(self.get_cloudspace()['status'], 'DEPLOYED')

        self.lg("%s ENDED" % self._testID)
