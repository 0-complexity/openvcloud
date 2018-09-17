from JumpScale.portal.docgenerator.popup import Popup


def main(j, args, params, tags, tasklet):
    import gevent

    actors = j.apps.cloudapi
    params.result = page = args.page
    cloudspaceId = args.getTag("cloudspaceId")
    timeout = gevent.Timeout(2)
    timeout.start()
    try:
        defenseinfo = actors.cloudspaces.getDefenseShield(cloudspaceId)
        defenseinfo["name"] = "autologin=%(user)s|%()s"
        page.addMessage(
            """<a href="javascript:window.open('%(url)s', 'autologin=%(user)s%%7c%(password)s');javascript:void(0);">Open Defenseshield</a>"""
            % defenseinfo
        )
    except:
        page.addMessage("N/A")
    finally:
        timeout.cancel()

    return params


def match(j, args, params, tags, tasklet):
    return True
