from JumpScale import j
import gevent

descr = """
Rollback a snapshot on a machine
"""

name = "rollbacksnapshot"
category = "libvirt"
organization = "greenitglobe"
author = "deboeckj@incubaid.com"
license = "bsd"
version = "2.0"
roles = []
async = True


def action(ovs_connection, diskguids, timestamp, name):
    ovs = j.clients.openvstorage.get(
        ips=ovs_connection["ips"],
        credentials=(ovs_connection["client_id"], ovs_connection["client_secret"]),
    )

    disk_path = "/vdisks/{}"
    if not name:
        for diskguid in diskguids:
            diskinfo = ovs.get(disk_path.format(diskguid))
            snapshots = reversed(diskinfo["snapshots"])
            for snapshot in snapshots:
                if int(timestamp) == int(snapshot["timestamp"]):
                    name = snapshot["label"]
                    break
            if name:
                break
        else:
            raise ValueError("Snapshot not found")

    path_rollback_snapshot = "/vdisks/{}/rollback"
    jobs = []
    for diskguid in diskguids:
        diskinfo = ovs.get(disk_path.format(diskguid))
        snapshots = reversed(diskinfo["snapshots"])
        for snapshot in snapshots:
            if snapshot["label"] == name:
                params = dict(timestamp=snapshot["timestamp"])
                jobs.append(
                    gevent.spawn(
                        ovs.post,
                        path_rollback_snapshot.format(diskguid),
                        params=params,
                    )
                )
                break

    gevent.joinall(jobs)

    for job in jobs:
        job.get()  # Reraises exception
    return True
