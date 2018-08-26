def main(j, args, params, tags, tasklet):
    acl = j.clients.agentcontroller.get()
    ccl = j.clients.osis.getNamespace("cloudbroker")
    wiki = []
    for location in ccl.location.search({})[1:]:
        wiki.append("h5. OpenvStorage {}".format(location["name"]))
        jobinfo = acl.executeJumpscript(
            "cloudscalers",
            "ovspackages",
            role="storagedriver",
            gid=location["gid"],
            timeout=10,
        )
        if jobinfo["state"] == "NOWORK":
            wiki.append("Not installed")
        elif jobinfo["state"] != "OK":
            wiki.append("Failed to retreive OVS version.")
        else:
            for name, version in jobinfo["result"].iteritems():
                wiki.append("* %s: %s" % (name, version))

    params.result = ("\n".join(wiki), args.doc)
    return params


def match(j, args, params, tags, tasklet):
    return True
