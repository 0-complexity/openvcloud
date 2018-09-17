def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    from JumpScale.portal.portal import exceptions

    params.result = (args.doc, args.doc)
    stackId = args.requestContext.params.get("id")

    try:
        stackId = int(stackId)
    except:
        return params
    stack = db.cloudbroker.stack.searchOne({"id": int(stackId)})
    if not stack:
        return params

    raise exceptions.Redirect(
        "/cbgrid/physicalNode?id={referenceId}&gid={gid}".format(**stack)
    )
