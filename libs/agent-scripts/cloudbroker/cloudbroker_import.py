from JumpScale import j

descr = """
Follow up creation of import
"""

name = "cloudbroker_import"
category = "cloudbroker"
organization = "greenitglobe"
author = "elawadim@greenitglobe.com"
license = "bsd"
version = "1.0"
roles = ["storagedriver"]
queue = "io"
async = True
timeout = 60 * 60 * 24


def action(link, username, passwd, path, machine):
    import tarfile
    from CloudscalerLibcloud import openvstorage
    from CloudscalerLibcloud.utils.webdav import WebDav, join, find_ova_files
    from JumpScale.core.system.streamchunker import StreamUnifier

    url = join(link, path)
    connection = WebDav(url, username, passwd)
    ovafiles = find_ova_files(connection)

    def get_ova_streams():
        for ovafile in ovafiles:
            yield connection.get(ovafile, stream=True).raw

    disks = [disk["file"] for disk in machine["disks"]]

    def extract(tar, ts=None):
        for member in tar:
            print("Iterating %s" % member.name)
            if member.name in disks:
                print("Processing %s" % member.name)
                ind = disks.index(member.name)
                disk = machine["disks"][ind]
                print("Extracting")
                tar.extract(member, ts.path)
                print("Converting")
                openvstorage.importVolume(
                    "%s/%s" % (ts.path, member.name), disk["referenceId"]
                )
                j.system.fs.remove("%s/%s" % (ts.path, member.name))

    with tarfile.open(mode="r|*", fileobj=StreamUnifier(get_ova_streams())) as tar:
        with openvstorage.TempStorage() as ts:
            extract(tar, ts)
    return machine


if __name__ == "__main__":
    machine = {
        "cpus": 1,
        "description": "test",
        "disks": [
            {
                "file": "disk-0.raw",
                "id": 12,
                "name": "vmdisk0",
                "path": "disk-0.raw",
                "size": 1073741824,
            }
        ],
        "id": 11,
        "mem": 134217728,
        "name": "lede",
    }
    print(
        action(
            "http://172.17.0.5/owncloud/remote.php/dav/files/admin/",
            "admin",
            "admin",
            "/export/",
            machine,
        )
    )
