def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    dtype_id = args.requestContext.params.get("id")
    if not dtype_id:
        args.doc.applyTemplate({})
        return params
    
    if not db.cloudbroker.disktype.exists(dtype_id):
        args.doc.applyTemplate({"dtype_id": None}, True)
        return params

    dtype = db.cloudbroker.disktype.getraw(dtype_id)
    
    args.doc.applyTemplate(dtype, True)

    return params


def match(j, args, params, tags, tasklet):
    return True
