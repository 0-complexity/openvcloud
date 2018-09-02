from JumpScale import j
from cloudbrokerlib.authenticator import auth
from JumpScale.portal.portal import exceptions
from JumpScale.portal.portal.async import async
from cloudbrokerlib.baseactor import BaseActor


class cloudbroker_node(BaseActor):
    def __init__(self):
        super(cloudbroker_node, self).__init__()
        self.scl = j.clients.osis.getNamespace("system")

    def _getNode(self, id):
        id = int(id) if isinstance(id, str) else id
        if not isinstance(id, int):
            raise exceptions.BadRequest("Node id should be either string or integer")
        node = self.scl.node.searchOne({"id": id})
        if not node:
            raise exceptions.NotFound("Node with id %s not found" % id)
        return node

    def unscheduleJumpscripts(self, nid, gid, name=None, category=None):
        self.cb.scheduleCmd(
            gid,
            nid,
            cmdcategory="jumpscripts",
            jscriptid=0,
            cmdname="unscheduleJumpscripts",
            args={"name": name, "category": category},
            queue="internal",
            log=False,
            timeout=120,
            roles=[],
        )

    def scheduleJumpscripts(self, nid, gid, name=None, category=None):
        self.cb.scheduleCmd(
            gid,
            nid,
            cmdcategory="jumpscripts",
            jscriptid=0,
            cmdname="scheduleJumpscripts",
            args={"name": name, "category": category},
            queue="internal",
            log=False,
            timeout=120,
            roles=[],
        )

    @auth(groups=["level2", "level3"])
    def maintenance(self, nid, vmaction, **kwargs):
        node = self._getNode(nid)
        kwargs["ctx"].events.runAsync(
            self._maintenance,
            args=(node, vmaction),
            kwargs=kwargs,
            title="Deactivating node",
            success="Successfully deactivated node",
            error="Failed to deactivate node",
        )

    def _maintenance(self, node, vmaction, **kwargs):
        if "storagedriver" in node["roles"]:
            j.apps.cloudbroker.ovsnode.deactivateNodes([node["id"]], **kwargs)
        if "cpunode" in node["roles"]:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(
                node["id"], node["gid"]
            )
            j.apps.cloudbroker.computenode.maintenance(
                stack["id"], node["gid"], vmaction, **kwargs
            )

    @auth(groups=["level2", "level3"])
    def enable(self, nid, message="", **kwargs):
        node = self._getNode(nid)
        kwargs["ctx"].events.runAsync(
            self._enable,
            args=(node, message),
            kwargs=kwargs,
            title="Enabling node",
            success="Successfully Enabled node",
            error="Failed to Enable node",
        )

    @auth(groups=["level2", "level3"])
    @async("Enable Nodes", "Finished enabling nodes", "Failed to enable nodes")
    def enableNodes(self, nids, message="", **kwargs):
        for nid in nids:
            node = self._getNode(nid)
            self._enable(node, message, **kwargs)

    def _enable(self, node, message="", **kwargs):
        if "storagedriver" in node["roles"]:
            j.apps.cloudbroker.ovsnode.activateNodes([node["id"]], **kwargs)
        if "cpunode" in node["roles"]:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(
                node["id"], node["gid"]
            )
            j.apps.cloudbroker.computenode.enable(
                stack["id"], node["gid"], message, **kwargs
            )

        gid = j.application.whoAmI.gid
        self.cb.executeJumpscript(
            "greenitglobe", "check_node_version", gid=gid, nid=node["id"]
        )

    @auth(groups=["level2", "level3"])
    def decomission(self, nid, vmaction, **kwargs):
        node = self._getNode(nid)
        gid = node["gid"]
        if "storagedriver" in node["roles"]:
            j.apps.cloudbroker.ovsnode.deactivateNodes([nid])
            self.cb.executeJumpscript(
                "cloudscalers", "ovs_put_node_offline", nid=nid, gid=gid
            )
        if "cpunode" in node["roles"]:
            stack = j.apps.cloudbroker.computenode._getStackFromNode(nid, gid)
            kwargs["ctx"].events.runAsync(
                j.apps.cloudbroker.computenode.maintenance,
                args=(stack["id"], gid, vmaction),
                kwargs=kwargs,
                title="Deactivating comppute node",
                success="Successfully deactivated compute node",
                error="Failed to deactivate compute node",
                errorcb="",
            )

    @auth(groups=["level2", "level3"])
    def execute_script(self, nid, gid, script):
        jobinfo = self.cb.executeJumpscript(
            "jumpscale", "exec", gid=gid, nid=nid, timeout=3600, args={"cmd": script}
        )
        if jobinfo["state"] == "ERROR":
            raise exceptions.Error("Failed to execute maintenance script")

    @auth(groups=["level2", "level3"])
    def applyIpmiAction(self, nid, action, **kwargs):
        if action not in ["power_on", "shutdown", "force_shutdown", "reboot"]:
            raise exceptions.BadRequest("Invalid action: {}".format(action))

        node = self._getNode(nid)
        nodename = node["name"].split(".")[0]
        args = {"cmd": "node action {} --name {}".format(action, nodename)}
        jobinfo = self.cb.executeJumpscript(
            "greenitglobe",
            "execute_installer_command",
            role="controllernode",
            gid=node["gid"],
            args=args,
        )

        if jobinfo["state"] == "OK":
            if jobinfo["result"]["return_code"]:
                raise exceptions.BadRequest(
                    "Failed to apply action: {} on node: {}.".format(action, nodename)
                )
        else:
            raise exceptions.ServiceUnavailable("Can't connect to management node.")
