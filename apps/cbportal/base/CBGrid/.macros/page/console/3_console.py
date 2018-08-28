from urlparse import urlparse


def main(j, args, params, tags, tasklet):
    params.result = page = args.page
    machineid = args.requestContext.params.get("id")
    try:
        machineid = int(machineid)
    except:
        pass
    if not isinstance(machineid, int):
        return params
    consoleurl = j.apps.cloudapi.machines.getConsoleUrl(int(machineid))
    parsedurl = urlparse(consoleurl)
    port = parsedurl.port
    if not port:
        port = 80 if parsedurl.scheme == "http" else 443
    path = "websockify?{}".format(parsedurl.query)
    host = parsedurl.hostname
    console = j.core.portal.active.templates.render(
        "cbportal/console.html", path=path, port=port, host=host
    )
    novncurl = "/g8vdc/.files/lib/noVNC/novnc.js"
    page.addJS(novncurl, header=True)
    page.addMessage(console)

    return params


def match(j, args, params, tags, tasklet):
    return True
