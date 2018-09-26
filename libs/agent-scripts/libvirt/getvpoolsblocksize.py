from JumpScale import j

descr = """
Libvirt script to returns vpools block sizes
"""

name = "getvpoolsblocksize"
category = "libvirt"
organization = "greenitglobe"
author = "ashraf.fouda@gig.tech"
license = "bsd"
version = "2.0"
roles = []
async = True


def action(ovs_connection):
    from CloudscalerLibcloud import openvstorage
    import re
    ovs = j.clients.openvstorage.get(
        ips=ovs_connection["ips"],
        credentials=(ovs_connection["client_id"], ovs_connection["client_secret"]),
    )

    vpools = dict()
    vpools_res = ovs.get("/vpools")
    for vpool in vpools_res["data"]:
        result = ovs.get("/vpools/{}".format(vpool), params={'contents': 'configuration'})
        name = result['name']
        name = re.sub(r'\d+', '', name)
        block_size = result['configuration']['cluster_size']
        vpools[name] = block_size

    return vpools


if __name__ == "__main__":
    import pprint

    scl = j.clients.osis.getNamespace("system")
    grid = scl.grid.get(j.application.whoAmI.gid)
    credentials = grid.settings["ovs_credentials"]
    credentials["ips"] = ["localhost"]
    pprint.pprint(action(credentials))
