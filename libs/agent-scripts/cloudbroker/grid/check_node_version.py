from JumpScale import j
import yaml

descr = """
This script checks node version, if it out of date, trigger update_node jumpscript to update it.
"""
organization = "greenitglobe"
category = "cloudbroker"
version = "1.0"
period = "0 12 1/2 * *"  # every 2 days at 12:00
startatboot = True
enable = True
roles = ["node"]
queue = "process"
log = True


def get_current_version():
    repos = dict()
    version = dict()
    repos.update(j.do.getGitReposListLocal("github", "jumpscale7"))
    repos.update(j.do.getGitReposListLocal("github", "0-complexity"))
    for path in repos.values():
        git = j.clients.git.get(path)
        slug = "{}/{}".format(git.account, git.name)
        version[slug] = dict([git.getBranchOrTag()])
    return version


def is_up_to_date(current, target):
    for repo in target["repos"]:
        slug = "/".join(repo["url"].split("/")[-2:])
        if slug not in current.keys():
            continue
        if current[slug] != repo["target"]:
            return False
    return True


def action():
    scl = j.clients.osis.getNamespace("system")
    status = scl.node.get(j.application.whoAmI.nid).status
    if not scl.version.count({"status": "INSTALLING"}) and status == "ENABLED":
        current = get_current_version()
        version = scl.version.searchOne({"status": "CURRENT"})
        target = yaml.load(version["manifest"])
        if not is_up_to_date(current, target):
            whoami = j.application.whoAmI
            nodename = scl.node.get(whoami.nid).name.split(".")[0]
            args = {"nodename": nodename}
            acl = j.clients.agentcontroller.get()
            acl.executeJumpscript(
                "greenitglobe",
                "update_node",
                role="controllernode",
                gid=whoami.gid,
                args=args,
                wait=False,
            )


if __name__ == "__main__":
    action()
