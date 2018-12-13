from JumpScale import j

descr = """
Runs the upgrade pod from the openvcloud_installer repo that upgrades the location.
"""

organization = "greenitglobe"
author = "tareka@greenitglobe.com"
license = "bsd"
version = "1.0"
category = "cloudbroker"
roles = ["controllernode"]
timeout = 120
order = 1
async = True


def action():
    """
    initiate upgrade
    """
    import yaml
    import requests

    scl = j.clients.osis.getNamespace("system")
    versionmodel = scl.version.searchOne({"status": "INSTALLING"})
    manifest = yaml.load(versionmodel["manifest"])
    manifest["version"] = versionmodel["name"]
    manifest["url"] = versionmodel["url"]

    try:
        with open("/tmp/versions-manifest.yaml", "w+") as file_descriptor:
            yaml.dump(manifest, file_descriptor)
            j.system.process.execute(
                "kubectl --kubeconfig /root/.kube/config create configmap --dry-run -o yaml --from-file=/tmp/versions-manifest.yaml versions-manifest |  kubectl --kubeconfig /root/.kube/config apply -f -"
            )
    finally:
        j.system.fs.remove("/tmp/versions-manifest.yaml")

    upgrader_data = manifest["upgrade"]
    _, output = j.system.process.execute("kubectl --kubeconfig /root/.kube/config get configmap system-config -o yaml")
    output = yaml.load(output)
    config = yaml.load(output["data"]["system-config.yaml"])
    rsgt_server = config["docker_registry"]["server"]
    for conttype in ("initContainers", "containers"):
        if conttype not in upgrader_data["spec"]["template"]["spec"]:
            continue
        for container in upgrader_data["spec"]["template"]["spec"][conttype]:
            container["image"] = "{}/{}:{}".format(
                rsgt_server,
                container["image"],
                manifest["images"][container["image"]],
            )

    try:
        with open("/tmp/upgrader-job.yaml", "w+") as file_descriptor:
            yaml.dump(upgrader_data, file_descriptor)
        j.system.process.execute(
            "kubectl apply --kubeconfig /root/.kube/config -f /tmp/upgrader-job.yaml",
            outputToStdout=True,
        )
    finally:
        j.system.fs.remove("/tmp/upgrader-job.yaml")


if __name__ == "__main__":
    print(action())