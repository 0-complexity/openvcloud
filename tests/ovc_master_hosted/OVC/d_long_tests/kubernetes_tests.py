import unittest, random, uuid, time
from ....utils.utils import BasicACLTest
from nose_parameterized import parameterized
from JumpScale import j
from JumpScale.portal.portal.PortalClient2 import ApiError
from JumpScale.baselib.http_client.HttpClient import HTTPError


class KubernetesTests(BasicACLTest):
    def setUp(self):
        super(KubernetesTests, self).setUp()

    def tearDown(self):
        super(KubernetesTests, self).tearDown()

    def kubectl_exec(self, cmd, nid):
        cmd = "kubectl --kubeconfig /root/.kube/config %s" % cmd
        return self.execute_command_on_physical_node(cmd, nid)

    def test01_kubernetes_selfhealing(self):
        """ OVC-053
        # *Test case for migrating running VFW by putting node in maintenance with action move or stop all vms.*

        **Test Scenario:**

        #. List all controller nodes.
        #. Choose random controller node to preform the test on it.
        #. Power off the target controller.
        #. Get all pods info.
        #. Check that all pods on the target controller node are moved to another node and running.
        """
        import ipdb ; ipdb.set_trace()
        acl = j.clients.agentcontroller.get()
        osiscl = j.clients.osis.getByInstance("main")
        nodecl = j.clients.osis.getCategory(osiscl, "system", "node")

        self.lg("List all controller nodes")
        query = {"roles": {"$in": ["controllernode"]}, '$fields':['id', 'name']}
        controller_nodes = nodecl.search(query)[1:]

        def get_pods():
            pods = dict()
            result = self.kubectl_exec("get po -o wide", controller_nodes[0]["id"]).strip()
            for item in result.split('\n')[1:]:
                pod = item.split()
                if 'mongo' in pod[0] or 'syncthing' in pod[0]:
                    pod_name = pod[0]
                else:
                    pod_name = '-'.join(pod[0].split('-')[:-2])
                if pod[2] == "UNKNOWN":
                    continue
                pods[pod_name] = {'status':pod[2], 'node':pod[6]}
            return pods

        self.lg("Choose random controller node to preform the test on it")
        pods = get_pods()
        target_controller = random.choice([node for node in controller_nodes if node['name'] != pods["qa"]["node"]])
        controller_nodes.remove(target_controller)

        try:
            self.lg("Power off target controller")
            acl.executeJumpscript(
                "greenitglobe",
                "execute_installer_command",
                role="controller",
                gid=j.application.whoAmI.gid,
                args={"cmd": "node action shutdown --name {}".format(target_controller["name"])},
                wait=True
            )

            time.sleep(7 * 60)

            _pods = [pod for pod in get_pods() if pod["status"] != "UNKNOWN"]
            for pod in pods.keys():
                self.assertIn(pod, _pods.keys())
                self.assertEqual(_pods[pod]["status"], pods[pod]["status"])
                self.assertNotEqual(_pods[pod]["node"], target_controller["name"])

        finally:
            self.lg("Power on target controller")
            acl.executeJumpscript(
                "greenitglobe",
                "execute_installer_command",
                role="controller",
                gid=j.application.whoAmI.gid,
                args={"cmd": "node action power_on --name {}".format(target_controller["name"])},
                wait=True
            )