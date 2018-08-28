from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    import netaddr

    params.result = page = args.page
    machineId = int(args.getTag("machineId"))
    ccl = j.clients.osis.getNamespace("cloudbroker")
    vmachine = ccl.vmachine.get(machineId)
    cloudspace = ccl.cloudspace.get(vmachine.cloudspaceId)
    accountId = cloudspace.accountId
    externalnetworks = list()

    def network_sort(pool):
        return "%04d_%s" % (pool["vlan"], pool["name"])

    for pool in sorted(
        ccl.externalnetwork.search({"accountId": {"$in": [accountId, 0]}})[1:],
        key=network_sort,
    ):
        network = netaddr.IPNetwork("{network}/{subnetmask}".format(**pool))
        externalnetworks.append(
            (
                "{name} - {network}".format(name=pool["name"], network=network),
                pool["id"],
            )
        )
    popup = Popup(
        id="attachexternal",
        header="Attach To External Network",
        submit_url="/restmachine/cloudbroker/machine/attachExternalNetwork",
    )
    popup.addDropdown("Choose External Network", "externalNetworkId", externalnetworks)
    popup.addHiddenField("machineId", machineId)
    popup.write_html(page)

    return params
