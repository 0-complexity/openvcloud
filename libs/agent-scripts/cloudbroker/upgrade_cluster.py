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

    def get_revision(branch, tag):
        match = ""
        if tag:
            match = "tags/{}".format(tag)
        elif branch:
            match = "heads/{}".format(branch)
        else:
            raise RuntimeError("No tag or branch set on repo")
        _, output = j.system.process.execute(
            "git ls-remote {}".format(ovc_installer_url)
        )
        for line in output.splitlines():
            if line.endswith(match):
                return line.split()[0]

    zero_complexity_path = "/opt/code/github/0-complexity/"
    repo_path = zero_complexity_path + "openvcloud_installer"
    scl = j.clients.osis.getNamespace("system")
    versionmodel = scl.version.searchOne({"status": "INSTALLING"})
    ovc_installer_url = "https://github.com/0-complexity/openvcloud_installer"
    manifest = yaml.load(versionmodel["manifest"])
    manifest["version"] = versionmodel["name"]
    manifest["url"] = versionmodel["url"]
    for repo in manifest["repos"]:
        if repo["url"] == ovc_installer_url:
            tag = repo["target"].get("tag")
            branch = repo["target"].get("branch")
            break

    try:
        with open("/tmp/versions-manifest.yaml", "w+") as file_descriptor:
            yaml.dump(manifest, file_descriptor)
            j.system.process.execute(
                "kubectl --kubeconfig /root/.kube/config create configmap --dry-run -o yaml --from-file=/tmp/versions-manifest.yaml versions-manifest |  kubectl --kubeconfig /root/.kube/config apply -f -"
            )
    finally:
        j.system.fs.remove("/tmp/versions-manifest.yaml")

    j.do.pullGitRepo(
        "https://github.com/0-complexity/openvcloud_installer/",
        ignorelocalchanges=True,
        reset=True,
        tag=tag,
        branch=branch,
    )
    with open(
        "{}/scripts/kubernetes/upgrader/upgrader-job.yaml".format(repo_path)
    ) as fil_desc:
        upgrader_data = yaml.load(fil_desc)

    for volume in upgrader_data["spec"]["template"]["spec"]["volumes"]:
        if (
            volume.get("gitRepo")
            and volume["gitRepo"]["repository"] == ovc_installer_url
        ):
            volume["gitRepo"]["revision"] = str(get_revision(branch, tag))
            break
    _, output = j.system.process.execute("kubectl --kubeconfig /root/.kube/config get configmap system-config -o yaml")
    output = yaml.load(output)
    file_key = output["data"].keys()[0]
    config = yaml.load(output["data"][file_key])
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
