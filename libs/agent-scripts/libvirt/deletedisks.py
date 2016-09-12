from JumpScale import j

descr = """
Libvirt script to delete a number of disks
"""

name = "deletedisks"
category = "libvirt"
organization = "greenitglobe"
author = "geert@greenitglobe.com"
license = "bsd"
version = "2.0"
roles = []
async = True


def action(ovs_connection, diskguids):
    # Deletes every disk in diskguids
    #
    # ovs_connection: dict holding connection info for ovs restapi
    #   eg: { ips: ['ip1', 'ip2', 'ip3'], client_id: 'dsfgfs', client_secret: 'sadfafsdf'}
    # diskguids: array of guids of the disks to delete
    #
    # returns None

    ovs = j.clients.openvstorage.get(ips=ovs_connection['ips'],
                                     credentials=(ovs_connection['client_id'],
                                                  ovs_connection['client_secret']))

    taskguids = (ovs.delete("/vdisks/{}".format(diskguid)) for diskguid in diskguids)
    for taskguid in taskguids:
        success, result = ovs.wait_for_task(taskguid)
        if not success:
            raise Exception("Could not delete disk:\n{}".format(result))

    return
