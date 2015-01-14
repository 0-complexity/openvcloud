from JumpScale.portal.docgenerator.popup import Popup

def main(j, args, params, tags, tasklet):
    params.result = page = args.page
    ccl = j.core.osis.getClientForNamespace('cloudbroker')
    vcl = j.core.osis.getClientForNamespace('vfw')
    scl = j.core.osis.getClientForNamespace('system')
    cloudspaceId = args.getTag('cloudspaceId')
    cloudspace = ccl.cloudspace.get(int(cloudspaceId))

    if cloudspace.status != 'DEPLOYED':
        popup = Popup(id='movevfw', header='CloudSpace is not deployed', submit_url='#')
        popup.write_html(page)
        return params

    vfwnodes = scl.node.search({'roles': 'fw', 'gid': cloudspace.gid})[1:]
    if len(vfwnodes) < 2:
        popup = Popup(id='movevfw', header='No other Firewall node available', submit_url='#')
        popup.write_html(page)
        return params

    popup = Popup(id='movevfw', header='Move Virtual Firewall', submit_url='/restmachine/cloudbroker/cloudspace/moveVirtualFirewallToFirewallNode')

    key = "%(gid)s_%(networkId)s" % cloudspace.dump()
    vfw = vcl.virtualfirewall.get(key)
    dropnodes = list()
    for node in vfwnodes:
        if node['id'] != vfw.nid or node['gid'] != vfw.gid:
            dropnodes.append(("FW Node %(name)s" % node, "%(id)s" % node))

    popup.addDropdown("FW Node to move to", 'targetNid', dropnodes)
    popup.addHiddenField('cloudspaceId', cloudspaceId)

    popup.write_html(page)

    return params


def match(j, args, params, tags, tasklet):
    return True
