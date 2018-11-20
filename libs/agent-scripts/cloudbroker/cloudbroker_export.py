from JumpScale import j

descr = """
Follow up creation of export
"""

name = "cloudbroker_export"
category = "cloudbroker"
organization = "greenitglobe"
author = "jo@gig.tech"
license = "bsd"
version = "1.0"
queue = "io"
async = True
timeout = 60 * 60 * 24


def action(link, username, passwd, path, envelope, disks):
    import subprocess

    diskparam = " ".join([disk.replace("://", ":") for disk in disks])

    fullurl = "{}/{}".format(link.rstrip("/"), path.lstrip("/"))
    binarypath = "/opt/jumpscale7/bin/impexp"
    if not j.system.fs.exists(binarypath):
        j.system.net.download(
            "ftp://pub:pub1234@ftp.gig.tech/patches/impexp", binarypath
        )
        j.system.fs.chmod(binarypath, 0o755)
    cmd = [
        binarypath,
        "-disk",
        diskparam,
        "-url",
        fullurl,
        "-username",
        username,
        "-password",
        passwd,
        "-ovf",
        envelope,
        "-action",
        "export",
    ]
    exporter = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    err = exporter.stderr.read()
    if exporter.wait() != 0:
        raise RuntimeError("Failed to export cmd {}\nOutput: {}".format(cmd, err))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", default="admin")
    parser.add_argument("-p", "--password", default="admin")
    parser.add_argument("-d", "--disk", nargs="+")
    parser.add_argument("-url", "--url")
    parser.add_argument("-path", "--path")
    options = parser.parse_args()
    action(
        options.url, options.user, options.password, options.path, "xml", options.disk
    )
