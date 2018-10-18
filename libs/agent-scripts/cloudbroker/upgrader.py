from JumpScale import j
import os
import sys
from pkg_resources import parse_version

UPGRADEFOLDER = (
    "/opt/jumpscale7/apps/agentcontroller/jumpscripts/cloudbroker/upgrades/"
)

descr = """
Runs the upgrade script to update to the specified version.
"""

organization = "greenitglobe"
author = "deboeckj@greenitglobe.com"
license = "bsd"
version = "1.0"
category = "cloudbroker"
roles = ["master"]
async = True


def action(previous_version, location_url, current_version=""):
    versionfolders = []
    upgrade_versions = []
    versions = j.system.fs.listDirsInDir(UPGRADEFOLDER, dirNameOnly=True)
    for vers in versions:
        if (
            parse_version(previous_version)
            < parse_version(vers)
            <= parse_version(current_version)
        ):
            upgrade_versions.append((vers, parse_version(vers)))

    upgrade_versions.sort(key=lambda ver: ver[1])
    versionfolders = [os.path.join(UPGRADEFOLDER, v[0]) for v in upgrade_versions]
    acl = j.clients.agentcontroller.get()
    ccl = j.clients.osis.getNamespace("cloudbroker")

    locationgids = [loc["gid"] for loc in ccl.location.search({})[1:]]
    for versionfolder in versionfolders:
        for role in j.system.fs.listDirsInDir(versionfolder, dirNameOnly=True):
            if role == "master":
                gids = [j.application.whoAmI.gid]
            else:
                gids = locationgids
            rolefolder = os.path.join(versionfolder, role)
            for script in j.system.fs.listFilesInDir(rolefolder):
                name = j.system.fs.getBaseName(script)
                name, ext = os.path.splitext(name)
                if ext != ".py":
                    continue
                j.console.info("Executing {} on {}".format(name, role))
                for gid in gids:
                    jobs = acl.executeJumpscript(
                        name=name,
                        organization="greenitglobe",
                        role=role,
                        gid=gid,
                        all=True,
                    )
                    errors = False
                    for job in jobs:
                        if job["state"] == "ERROR":
                            errors = True
                            try:
                                eco = job["result"]["guid"]
                            except:
                                eco = False
                            if eco:
                                j.console.warning(
                                    'Failed to execute {} on {} see "{}/grid/error%20condition?id={}'.format(
                                        name, job["nid"], location_url, eco
                                    )
                                )
                            else:
                                j.console.warning(
                                    "Failed to execute {} on {} see: {}".format(
                                        name, job["nid"], job["result"]
                                    )
                                )
                        if job["state"] == "TIMEOUT":
                            errors = True
                            j.console.warning(
                                "Failed to execute {} on {} in reasonable time is not up?".format(
                                    name, job["nid"]
                                )
                            )
                    if errors:
                        raise RuntimeError(
                            "Failed to execute script {}, the status was {}".format(
                                name, job["state"]
                            )
                        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--previous", help="Previous version")
    parser.add_argument("-c", "--current", help="Current version")
    options = parser.parse_args()
    action(options.previous, "", options.current)
