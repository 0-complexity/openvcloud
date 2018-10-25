import unittest, random, uuid
from ....utils.utils import BasicACLTest, VMClient, execute_async_ovc
from nose_parameterized import parameterized
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError
from JumpScale import j
import time
import threading
import os, requests
import json
import gevent


class MachineLongTests(BasicACLTest):
    def setUp(self):
        super(MachineLongTests, self).setUp()
        self.default_setup()

    # @unittest.skip('https://github.com/0-complexity/openvcloud/issues/1130')
    def test01_export_import_vm(self):
        """ OVC-048
        *Test case for checking cloned VM ip, portforwards and credentials*

        **Test Scenario:**

        #. Create virtual machine (VM1), should succeed.
        #. Create data disk (DD1), should succeed.
        #. Attach disk (DD1) to virtual machine (VM1), should succeed.
        #. Write file (F1) on the boot disk of the virtual machine (VM1), should succeed.
        #. Write file (F2) on the data disk of the virtual machine (VM1), should succeed.
        #. Export virtual machine (VM1), should succeed.
        #. Import virtual machine (VM1), should succeed.
        #. Check that file (F1) exists in the imported virtual machine.
        #. Check that file (F2) exists in the imported virtual machine's data disk (DD1).
        """
        scl = j.clients.osis.getNamespace("system")
        grid = scl.grid.get(j.application.whoAmI.gid)
        ovs_cred = grid.settings["ovs_credentials"]
        ovs = j.clients.openvstorage.get(ips=ovs_cred["ips"], credentials=(ovs_cred["client_id"], ovs_cred["client_secret"]))
        self.lg("Create virtual machine (VM1), should succeed")
        machine_1_id = self.cloudapi_create_machine(self.cloudspace_id)

        self.lg("Create data disk (DD1), should succeed")
        disk_id = self.create_disk(self.account_id)

        self.lg("Attach disk (DD1) to virtual machine (VM1), should succeed")
        response = self.api.cloudapi.machines.attachDisk(
            machineId=machine_1_id, diskId=disk_id
        )
        self.assertTrue(response)

        self.lg(
            "Write file (F1) on the boot disk of the virtual machine (VM1), should succeed"
        )
        machine_1_client = VMClient(machine_1_id)
        machine_1_client.execute('echo "helloWorld" > test1.txt')

        self.lg(
            "Write file (F2) on the data disk of the virtual machine (VM1), should succeed"
        )
        machine_1_client.execute("mkdir data")
        machine_1_client.execute("mkfs.ext4 /dev/vdb", sudo=True)
        machine_1_client.execute("mount /dev/vdb data", sudo=True)
        machine_1_client.execute("chown ${USER}:${USER} data", sudo=True)
        machine_1_client.execute('echo "helloWorld" > data/test2.txt')

        time.sleep(40)

        folder_name = str(uuid.uuid4()).replace("-", "")[:10]
        owncloud_auth = (self.owncloud_user, self.owncloud_password)

        web_dav_link = self.owncloud_url + "/remote.php/webdav/"

        folder_url = "{url}/remote.php/dav/files/{user}/{folder}".format(
            url=self.owncloud_url, user=self.owncloud_user, folder=folder_name
        )

        self.lg("Create folder in owncloud")
        requests.request("MKCOL", url=folder_url, auth=owncloud_auth)
        disks = [disk for disk in machine_1_client.machine["disks"] if disk["type"] != "M" ]

        try:
            self.lg("Export virtual machine (VM1), should succeed")
            response = self.api.cloudapi.machines.exportOVF(
                link=web_dav_link,
                machineId=machine_1_id,
                username=self.owncloud_user,
                passwd=self.owncloud_password,
                path=folder_name,
            )

            self.assertTrue(response)

            for disk in disks:
                query = dict(type="AND", items=[("name", "EQUALS", "export/clonefordisk_{}".format(disk["referenceId"].split("@")[1]))])
                result = ovs.get(
                    "/vdisks", params=dict(contents="name,devicename", query=json.dumps(query))
                )
                self.assertEqual(result['data'], [])

            time.sleep(300)

            self.lg("Import virtual machine (VM2), should succeed")
            self.api.cloudapi.machines.importOVF(
                link=web_dav_link,
                username=self.owncloud_user,
                passwd=self.owncloud_password,
                path=folder_name,
                cloudspaceId=self.cloudspace_id,
                name="imported_vm",
                sizeId=2,
            )

            machines = self.api.cloudbroker.machine.list(
                cloudspaceId=self.cloudspace_id
            )
            imported_vm_id = [i["id"] for i in machines if i["id"] != machine_1_id]

            if not imported_vm_id:
                self.fail("can't import vm")

            imported_vm_id = imported_vm_id[0]

            self.wait_for_status(
                "RUNNING", self.api.cloudapi.machines.get, machineId=imported_vm_id
            )

            imported_vm_info = self.api.cloudapi.machines.get(machineId=imported_vm_id)
            self.assertTrue(all([x["name"] for x in imported_vm_info["disks"]]))

            self.lg("Check that file (F1) exists in the imported virtual machine")
            imported_vm_client = VMClient(
                imported_vm_id,
                login=machine_1_client.login,
                password=machine_1_client.password,
                timeout=120,
            )

            stdin, stdout, stderr = imported_vm_client.execute("cat test1.txt")
            self.assertIn("helloWorld", stdout.read())

            self.lg(
                "Check that file (F2) exists in the imported virtual machine's data disk (DD1)"
            )
            imported_vm_client.execute("mount /dev/vdb data", sudo=True)
            stdin, stdout, stderr = imported_vm_client.execute("cat data/test2.txt")
            self.assertIn("helloWorld", stdout.read())

        except:
            raise

        finally:
            self.lg("Delete folder in owncloud")
            requests.request("DELETE", url=folder_url, auth=owncloud_auth)

    def test02_mass_vms_creation(self):
        # create account
        """ OVC-049

        *Test case for mass vms creationg 100 vm*

        **Test Scenario:**

        #. create 100 vms
        #. make sure all are in RUNNING state
        """

        def get_vm_name(cloudspace_id, counter):
            return "vm-mass-{0}-{1:0>3}".format(cloudspace_id, counter)

        jobs = []
        # Create vms in this cloud space
        expected_vms = [get_vm_name(self.cloudspace_id, x) for x in range(1, 101)]
        self.lg("Creating 100 machine")
        for name in expected_vms:
            jobs.append(
                self.cloudapi_create_machine(
                    cloudspace_id=self.cloudspace_id,
                    name=name,
                    memory=512,
                    vcpus=1,
                    disksize=10,
                    async=True,
                )
            )
        machines_ids = []
        gevent.wait()
        for job in jobs:
            machines_ids.append(job.get())
        jobs = []
        status = set()
        for machine_id in machines_ids:
            jobs.append(
                execute_async_ovc(
                    self.api.portalclient2,
                    self.api.portalclient2.cloudbroker.machine.get,
                    machineId=machine_id,
                )
            )
        gevent.wait()
        for job in jobs:
            status.add(job.get()["status"])
        self.lg("Make sure all are in RUNNING state")
        self.assertEqual(len(status), 1)
        self.assertEqual(status.pop(), "RUNNING")
