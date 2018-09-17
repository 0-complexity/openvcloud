def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    gid = args.requestContext.params.get("gid")
    try:
        gid = int(gid)  # check like this to prevent long conversion error
    except:
        pass
    if not isinstance(gid, int):
        args.doc.applyTemplate({})
        return params

    gid = int(gid)

    locations = db.cloudbroker.location.search({"gid": gid})[1:]
    if not locations:
        args.doc.applyTemplate({"gid": None}, True)
        return params

    obj = locations[0]
    args.doc.applyTemplate(obj, True)
    return params


def match(j, args, params, tags, tasklet):
    return True
