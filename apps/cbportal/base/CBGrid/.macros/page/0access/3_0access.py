def main(j, args, params, tags, tasklet):
    from cloudbrokerlib.cloudbroker import db
    from jose import jwt as jose_jwt
    from JumpScale.portal.portal import exceptions
    import json

    page = args.page
    modifier = j.html.getPageModifierGridDataTables(page)

    oauth = j.clients.oauth.get(instance="itsyouonline")
    try:
        jwt = oauth.get_active_jwt(session=args.requestContext.env["beaker.session"])
    except:
        raise exceptions.NotFound("Page not found")
    if jwt:
        jwt_data = jose_jwt.get_unverified_claims(jwt)
        jwt_data = json.loads(jwt_data)
        scope = "user:memberof:{}.0-access".format(oauth.id)
        if scope not in jwt_data["scope"]:
            raise exceptions.NotFound("Page not found")

    nodes = []
    for node_id in db.system.node.list():
        node = db.system.node.get(node_id)
        ip = ""
        if "master" in node.roles:
            continue
        else:
            _, ip = j.apps.cloudbroker.zeroaccess._get_node_info(node_id)
            if not ip:
                continue

        name = '<a href="/cbgrid/0-access Node?node={id}">{name}</a>'.format(
            name=node.name, id=node_id
        )
        nodes.append([node.id, name, ip])
    mgmt_name, mgmt_ip = j.apps.cloudbroker.zeroaccess._get_node_info("0")
    name = '<a href="/cbgrid/0-access Node?node={id}">{name}</a>'.format(
        name=mgmt_name, id="0"
    )
    nodes.append(["0", name, mgmt_ip])

    fieldnames = ["ID", "Name", "IP"]
    if nodes:
        page.addList(nodes, fieldnames)
    else:
        page.addList([["Can not list nodes", "", ""]], fieldnames)

    params.result = page
    return params


def match(j, args, params, tags, tasklet):
    return True
