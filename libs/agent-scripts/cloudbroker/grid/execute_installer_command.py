from JumpScale import j

descr = """
This script executes installer commands on mangement pod
"""

category = "cloudbroker"
organization = "greenitglobe"
license = "bsd"
version = "1.0"
roles = []
async = True


def get_client():
    cmd = "kubectl --kubeconfig /root/.kube/config get service management-ssh -o=jsonpath='{.spec.clusterIP}'"
    host = j.system.process.execute(cmd)[1]
    client = j.remote.cuisine.connect(host, 22)
    return client


def action(cmd):
    client = get_client()
    response = client.run("installer {}".format(cmd), warn_only=True)
    return dict(
        return_code=response.return_code, stdout=response.stdout, stderr=response
    )
