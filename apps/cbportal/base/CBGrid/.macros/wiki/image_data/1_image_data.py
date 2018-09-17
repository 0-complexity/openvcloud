def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db

    params.result = (args.doc, args.doc)
    imageid = args.requestContext.params.get("id")
    if not imageid:
        args.doc.applyTemplate({})
        return params
    try:
        imageid = int(imageid)
    except ValueError:
        args.doc.applyTemplate({})
        return params

    if not db.cloudbroker.image.exists(imageid):
        args.doc.applyTemplate({"imageid": None}, True)
        return params

    image = db.cloudbroker.image.getraw(imageid)
    if image["accountId"]:
        query = {"$fields": ["id", "name"], "$query": {"id": image["accountId"]}}
        image["account"] = db.cloudbroker.account.searchOne(query)

    args.doc.applyTemplate(image, True)

    return params


def match(j, args, params, tags, tasklet):
    return True
