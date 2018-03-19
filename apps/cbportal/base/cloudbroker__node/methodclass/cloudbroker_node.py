from JumpScale import j
from JumpScale.portal.portal.auth import auth
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor, wrap_remote


class cloudbroker_node(BaseActor):
    def __init__(self):
        super(cloudbroker_node, self).__init__()
        self.scl = j.clients.osis.getNamespace('system')
        self.acl = j.clients.agentcontroller.get()

    def _getNode(self, id):
        id = int(id) if isinstance(id, str) else id
        if not isinstance(id, int):
            raise exceptions.BadRequest('Node id should be either string or integer')
        node = self.scl.node.searchOne({'id': id})
        if not node:
            raise exceptions.NotFound('Node with id %s not found' % id)
        return node

    def unscheduleJumpscripts(self, nid, gid, name=None, category=None):
        self.acl.scheduleCmd(gid, nid, cmdcategory="jumpscripts", jscriptid=0,
                            cmdname="unscheduleJumpscripts", args={'name': name, 'category': category},
                            queue="internal", log=False, timeout=120, roles=[])

    def scheduleJumpscripts(self, nid, gid, name=None, category=None):
        self.acl.scheduleCmd(gid, nid, cmdcategory="jumpscripts", jscriptid=0,
                            cmdname="scheduleJumpscripts", args={'name': name, 'category': category},
                            queue="internal", log=False, timeout=120, roles=[])

    @auth(['level2', 'level3'], True)
    @wrap_remote
    def maintenance(self, nid, gid, vmaction, **kwargs):
        node = self._getNode(nid)
        if 'storagedriver' in node['roles']:
            kwargs['ctx'].events.runAsync(j.apps.cloudbroker.ovsnode.deactivateNodes,
                                          args=([nid],),
                                          kwargs=kwargs,
                                          title='Deactivating storage node',
                                          success='Successfully deactivated storage node',
                                          error='Failed to deactivate storage node ',
                                          errorcb='')
        if 'cpunode' in node['roles']:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(nid, gid)
            kwargs['ctx'].events.runAsync(j.apps.cloudbroker.computenode.maintenance, 
                                          args=(stack['id'], gid, vmaction),
                                          kwargs=kwargs,
                                          title='Deactivating compute node',
                                          success='Successfully deactivated compute node',
                                          error='Failed to deactivate compute node',
                                          errorcb='')
            

    @auth(['level2', 'level3'], True)
    @wrap_remote
    def enable(self, nid, gid, message='', **kwargs):
        node = self._getNode(nid)
        if 'storagedriver' in node['roles']:
            nids = [nid]
            kwargs['ctx'].events.runAsync(j.apps.cloudbroker.ovsnode.activateNodes,
                                          args=([nid],),
                                          kwargs=kwargs,
                                          title='Enabling storage node',
                                          success='Successfully Enabled storage node',
                                          error='Failed to Enable storage node ',
                                          errorcb='')
        if 'cpunode' in node['roles']:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(nid, gid)
            kwargs['ctx'].events.runAsync(j.apps.cloudbroker.computenode.enable,
                                          args=(stack['id'], gid, message),
                                          kwargs=kwargs,
                                          title='Enabling compute node',
                                          success='Successfully Enabled compute node',
                                          error='Failed to Enable compute node ',
                                          errorcb='')

    @auth(['level2', 'level3'], True)
    @wrap_remote
    def decomission(self, nid, gid, vmaction, **kwargs):
        node = self._getNode(nid)
        if 'storagedriver' in node['roles']:
            j.apps.cloudbroker.ovsnode.deactivateNodes([nid])
            self.acl.executeJumpscript('cloudscalers', 'ovs_put_node_offline', nid=nid, gid=gid)
        if 'cpunode' in node['roles']:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(nid, gid)
            kwargs['ctx'].events.runAsync(j.apps.cloudbroker.computenode.maintenance, 
                                          args=(stack['id'], gid, vmaction),
                                          kwargs=kwargs,
                                          title='Deactivating comppute node',
                                          success='Successfully deactivated compute node',
                                          error='Failed to deactivate compute node',
                                          errorcb='')

    @auth(['level2', 'level3'], True)
    def execute_script(self, nid, gid, script):
        jobinfo = self.acl.executeJumpscript('jumpscale', 'exec',
                                       gid=gid, nid=nid,
                                       timeout=3600,
                                       args={'cmd':script})
        if jobinfo['state'] == 'ERROR':
            raise exceptions.Error("Failed to execute maintenance script")