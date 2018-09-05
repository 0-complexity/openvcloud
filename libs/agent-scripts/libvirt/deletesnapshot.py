from JumpScale import j
import gevent

descr = """
Delete snapshot of machine
"""

name = "deletesnapshot"
category = "libvirt"
organization = "greenitglobe"
author = "geert@greenitglobe.com"
license = "bsd"
version = "2.0"
roles = []
async = True


def action(ovs_connection, diskguids, timestamp, name):
    # Delete snapshot
    #
    # ovs_connection: dict holding connection info for ovs restapi
    #   eg: { ips: ['ip1', 'ip2', 'ip3'], client_id: 'dsfgfs', client_secret: 'sadfafsdf'}
    # diskguids: array of guids of the disks to delete
    # timestamp: epoch timestamp when the snapshot was created (integer)
    #
    # returns None

    ovs = j.clients.openvstorage.get(
        ips=ovs_connection["ips"],
        credentials=(ovs_connection["client_id"], ovs_connection["client_secret"]),
    )
    path_get_disk = "/vdisks/{}"
    path_delete_snapshot = "/vdisks/{}/remove_snapshot"

    if not name:
        for diskguid in diskguids:
            diskinfo = ovs.get(path_get_disk.format(diskguid))
            snapshots = reversed(diskinfo["snapshots"])
            for snapshot in snapshots:
                if timestamp == snapshot["timestamp"]:
                    name = snapshot["label"]
                    break
            if name:
                break
        else:
            raise ValueError("Snapshot not found")

    def delete_snapshot(diskguid):
        # First lookup snapshot
        disk_details = ovs.get(path_get_disk.format(diskguid))
        snapshot = next(
            (x for x in disk_details["snapshots"] if x["label"] == name), None
        )
        if snapshot is None:
            raise ValueError("Snapshot not found")

        # Delete snapshots
        taskguid = ovs.post(
            path_delete_snapshot.format(diskguid),
            params=dict(snapshot_id=snapshot["guid"]),
        )
        success, result = ovs.wait_for_task(taskguid)
        if not success:
            raise Exception("Could not delete snapshot:\n{}".format(result))

    jobs = [gevent.spawn(delete_snapshot, diskguid) for diskguid in diskguids]
    gevent.joinall(jobs)
    for job in jobs:
        job.get()  # Reraises exception
    return


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--diskguid")
    parser.add_argument("-t", "--timestamp", type=int)
    options = parser.parse_args()
    scl = j.clients.osis.getNamespace("system")
    ovs_credentials = scl.grid.get(j.application.whoAmI.gid).settings["ovs_credentials"]
    print(action(ovs_credentials, [options.diskguid], options.timestamp, None))
