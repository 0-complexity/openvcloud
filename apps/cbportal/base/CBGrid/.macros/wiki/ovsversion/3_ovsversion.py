def main(j, args, params, tags, tasklet):
    acl = j.clients.agentcontroller.get()
    jobinfo = acl.executeJumpscript('cloudscalers', 'ovspackages', role='storagenode', gid=j.application.whoAmI.gid)
    wiki = []
    for name, version in jobinfo['result'].iteritems():
        wiki.append("* %s: %s" % (name, version))

    params.result = ('\n'.join(wiki), args.doc)
    return params

def match(j, args, params, tags, tasklet):
    return True
