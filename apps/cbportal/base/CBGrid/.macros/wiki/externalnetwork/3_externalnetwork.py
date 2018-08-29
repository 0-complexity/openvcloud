def main(j, args, params, tags, tasklet):

    params.result = (args.doc, args.doc)
    networkid = args.requestContext.params.get("networkid")
    try:
        networkid = int(networkid)
    except:
        pass
    if not isinstance(networkid, int):
        args.doc.applyTemplate({})
        return params

    cbclient = j.clients.osis.getNamespace("cloudbroker")
    if not cbclient.externalnetwork.exists(networkid):
        args.doc.applyTemplate({}, True)
        return params

    pool = cbclient.externalnetwork.get(networkid)
    networkinfo = j.apps.cloudbroker.iaas.getUsedIPInfo(pool)
    network = pool.dump()
    network["pingips"] = ",".join(network["pingips"])
    network.update(networkinfo)

    args.doc.applyTemplate(network, True)
    return params


def match(j, args, params, tags, tasklet):
    return True
