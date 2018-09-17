from JumpScale import j
from cloudbrokerlib.authenticator import auth
import functools
import time
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor


class cloudbroker_computenode(BaseActor):
    """
    Operator actions for handling interventsions on a computenode
    """

    def __init__(self):
        super(cloudbroker_computenode, self).__init__()
        self._vcl = j.clients.osis.getCategory(
            j.core.portal.active.osis, "vfw", "virtualfirewall"
        )
        self.node = j.apps.cloudbroker.node

    def _getStack(self, id, gid):
        stack = self.models.stack.searchOne({"id": int(id), "gid": int(gid)})
        if not stack:
            raise exceptions.NotFound("ComputeNode with id %s not found" % id)
        return stack

    def _getStackFromNode(self, nid, gid):
        nid = nid if isinstance(nid, str) else str(nid)
        stack = self.models.stack.searchOne({"referenceId": nid, "gid": int(gid)})
        if not stack:
            raise exceptions.NotFound("ComputeNode with id %s not found" % id)
        return stack

    def setStatus(self, id, gid, status, **kwargs):
        """
        Set different stack statusses, options are 'ENABLED(creation and actions on machines is possible)','DISABLED(Only existing machines are started)', 'OFFLINE(Machine is not available'
        param:statckid id of the stack to update
        param:status status e.g ENABLED, DISABLED, or OFFLINE
        result
        """
        statusses = ["ENABLED", "DECOMMISSIONED", "MAINTENANCE"]
        stack = self._getStack(id, gid)
        if status not in statusses:
            return exceptions.BadRequest(
                "Invalid status %s should be in %s" % (status, ", ".join(statusses))
            )
        if status == "ENABLED":
            if stack["status"] not in ("MAINTENANCE", "ENABLED", "ERROR"):
                raise exceptions.PreconditionFailed(
                    "Can not enable ComputeNode in state %s" % (stack["status"])
                )

        if status == "DECOMMISSIONED":
            return self.decommission(id, gid, "")

        elif status == "MAINTENANCE":
            return self.maintenance(id, gid, vmaction="move")
        else:
            return self._changeStackStatus(stack, status)

    def _changeStackStatus(self, stack, status):
        stack["status"] = status
        if status == "ENABLED":
            stack["eco"] = None
        self.models.stack.set(stack)
        if status in ["ENABLED", "MAINTENANCE", "DECOMMISSIONED", "ERROR"]:
            nodes = self.sysmodels.node.search(
                {"id": int(stack["referenceId"]), "gid": stack["gid"]}
            )[1:]
            if len(nodes) > 0:
                node = nodes[0]
                node["status"] = status
                self.sysmodels.node.set(node)
        return stack["status"]

    def _errorcb(self, stack, eco):
        stack["status"] = "ERROR"
        stack["eco"] = eco.guid
        self.models.stack.set(stack)

    def list(self, gid=None, **kwargs):
        query = {}
        if gid:
            query["gid"] = gid
        return self.models.stack.search(query)[1:]

    def enableStacks(self, ids, **kwargs):
        kwargs["ctx"].events.runAsync(
            self._enableStacks,
            args=(ids,),
            kwargs=kwargs,
            title="Enabling Stacks",
            success="Successfully Scheduled Stacks Enablement",
            error="Failed to Enable Stacks",
        )

    def _enableStacks(self, ids, **kwargs):
        for stackid in ids:
            stack = self.models.stack.get(stackid)
            self.enable(stack.id, stack.gid, "", **kwargs)

    def enable(self, id, gid, message="", **kwargs):
        title = "Enabling Stack"
        stack = self._getStack(id, gid)
        errorcb = functools.partial(self._errorcb, stack)
        status = self._changeStackStatus(stack, "ENABLED")
        startmachines = []
        machines = self._get_stack_machines(id)
        # loop on machines and get those that were running (have 'start' in tags)
        for machine in machines:
            tags = j.core.tags.getObject(machine["tags"])
            if tags.labelExists("start"):
                startmachines.append(machine["id"])
        if startmachines:
            j.apps.cloudbroker.machine.startMachines(
                startmachines, "", ctx=kwargs["ctx"]
            )

        kwargs["ctx"].events.runAsync(
            self._start_vfws,
            args=(stack, title, kwargs["ctx"]),
            kwargs={},
            title="Starting virtual Firewalls",
            success="Successfully started all Virtual Firewalls",
            error="Failed to Start Virtual Firewalls",
            errorcb=errorcb,
        )
        self.node.scheduleJumpscripts(
            int(stack["referenceId"]), gid, category="monitor.healthcheck"
        )
        return status

    def _get_stack_machines(self, stackId, fields=None):
        querybuilder = {}
        if fields:
            querybuilder["$fields"] = fields
        querybuilder["$query"] = {
            "stackId": stackId,
            "status": {"$nin": ["DESTROYED", "ERROR"]},
        }
        machines = self.models.vmachine.search(querybuilder)[1:]
        return machines

    def maintenance(self, id, gid, vmaction, **kwargs):
        """
        :param id: stack Id
        :param gid: Grid id
        :param vmaction: what to do with vms stop or move
        :return: bool
        """
        if vmaction not in ("move", "stop"):
            raise exceptions.BadRequest("VMAction should either be move or stop")
        stack = self._getStack(id, gid)
        errorcb = functools.partial(self._errorcb, stack)
        self._changeStackStatus(stack, "MAINTENANCE")
        title = "Putting Node in Maintenance"
        stackmachines = self._get_stack_machines(
            stack["id"], ["id", "status", "tags", "name", "disks"]
        )
        if vmaction == "stop":
            machines_actor = j.apps.cloudbroker.machine
            for machine in stackmachines:
                if machine["status"] == "RUNNING":
                    if "start" not in machine["tags"].split(" "):
                        machines_actor.tag(machine["id"], "start")

            kwargs["ctx"].events.runAsync(
                self._stop_vfws,
                args=(stack, title, kwargs["ctx"]),
                kwargs={},
                title="Stopping virtual Firewalls",
                success="Successfully Stopped all Virtual Firewalls",
                error="Failed to Stop Virtual Firewalls",
                errorcb=errorcb,
            )

            machineIds = [machine["id"] for machine in stackmachines]
            machines_actor.stopMachines(machineIds, "", ctx=kwargs["ctx"])
        elif vmaction == "move":
            move_vms = []
            system_vfwid = None
            for stackmachine in stackmachines:
                if (
                    self.models.disk.count(
                        {"id": {"$in": stackmachine["disks"]}, "type": "P"}
                    )
                    == 0
                ):
                    move_vms.append(stackmachine)
                else:
                    system_vfwid = self.models.cloudspace.searchOne(
                        {"id": stackmachine["cloudspaceId"]}
                    )["networkId"]
            kwargs["ctx"].events.runAsync(
                self._move_virtual_machines,
                args=(stack, title, kwargs["ctx"], move_vms, system_vfwid),
                kwargs={},
                title="Putting Node in Maintenance",
                success="Successfully moved all Virtual Machines",
                error="Failed to move Virtual Machines",
                errorcb=errorcb,
            )
        node_id = int(stack["referenceId"])
        self.cb.executeJumpscript("cloudscalers", "nodestatus", nid=node_id, gid=gid)
        self.node.unscheduleJumpscripts(node_id, gid, category="monitor.healthcheck")
        time.sleep(5)
        self.sysmodels.health.deleteSearch({"nid": node_id})
        return True

    def unscheduleJumpscripts(self, stack_id, gid, name=None, category=None):
        stack = self._getStack(stack_id, gid)
        self.cb.scheduleCmd(
            gid,
            int(stack["referenceId"]),
            cmdcategory="jumpscripts",
            jscriptid=0,
            cmdname="unscheduleJumpscripts",
            args={"name": name, "category": category},
            queue="internal",
            log=False,
            timeout=120,
            roles=[],
        )

    def scheduleJumpscripts(self, stack_id, gid, name=None, category=None):
        stack = self._getStack(stack_id, gid)
        self.cb.scheduleCmd(
            gid,
            int(stack["referenceId"]),
            cmdcategory="jumpscripts",
            jscriptid=0,
            cmdname="scheduleJumpscripts",
            args={"name": name, "category": category},
            queue="internal",
            log=False,
            timeout=120,
            roles=[],
        )

    def _stop_vfws(self, stack, title, ctx):
        vfws = self._vcl.search(
            {"gid": stack["gid"], "nid": int(stack["referenceId"])}
        )[1:]
        for vfw in vfws:
            ctx.events.sendMessage(title, "Stopping Virtual Firewal %s" % vfw["id"])
            self.cb.netmgr.fw_stop(vfw["guid"])

    def _start_vfws(self, stack, title, ctx):
        vfws = self._vcl.search(
            {"gid": stack["gid"], "nid": int(stack["referenceId"])}
        )[1:]
        for vfw in vfws:
            ctx.events.sendMessage(title, "Starting Virtual Firewal %s" % vfw["id"])
            self.cb.netmgr.fw_start(vfw["guid"])

    def _move_virtual_machines(
        self, stack, title, ctx, stackmachines, exclude_vfwid=None
    ):
        machines_actor = j.apps.cloudbroker.machine
        othernodes = self.sysmodels.node.search(
            {"gid": stack["gid"], "status": "ENABLED", "roles": "fw"}
        )[1:]
        if not othernodes:
            raise exceptions.ServiceUnavailable(
                "There is no other Firewall node available to move the Virtual Firewall to"
            )

        for machine in stackmachines:
            ctx.events.sendMessage(title, "Moving Virtual Machine %s" % machine["name"])
            try:
                machines_actor.moveToDifferentComputeNode(
                    machine["id"], reason="Disabling source", force=True
                )
            except Exception as e:
                j.errorconditionhandler.processPythonExceptionObject(e)

        vfws = self._vcl.search(
            {
                "gid": stack["gid"],
                "nid": int(stack["referenceId"]),
                "id": {"$ne": exclude_vfwid},
            }
        )[1:]
        for vfw in vfws:
            nid = int(
                self.cb.getBestStack(
                    stack["gid"], excludelist=[stack["id"]], memory=128
                )["referenceId"]
            )
            ctx.events.sendMessage(title, "Moving Virtual Firewal %s" % vfw["id"])
            if not self.cb.netmgr.fw_move(vfw["guid"], nid):
                try:
                    self.cb.netmgr.fw_delete(
                        fwid=vfw["guid"], deletemodel=False, timeout=20
                    )
                except exceptions.ServiceUnavailable:
                    # agent on node is probably not running lets just start it somewhere else
                    pass
                self.cb.netmgr.fw_start(vfw["guid"], targetNid=nid)

    @auth(groups=["level2", "level3"])
    def decommission(self, id, gid, message, **kwargs):
        stack = self._getStack(id, gid)
        stacks = self.models.stack.search({"gid": gid, "status": "ENABLED"})[1:]
        if not stacks:
            raise exceptions.PreconditionFailed(
                "Decommissioning stack not possible when there are no other enabled stacks"
            )
        self._changeStackStatus(stack, "DECOMMISSIONED")
        ctx = kwargs["ctx"]
        title = "Decommissioning Node"
        errorcb = functools.partial(self._errorcb, stack)
        stackmachines = self._get_stack_machines(stack["id"], ["id", "name"])
        ctx.events.runAsync(
            self._move_virtual_machines,
            args=(stack, title, ctx, stackmachines),
            kwargs={},
            title=title,
            success="Successfully moved all Virtual Machines.</br>Decommissioning finished.",
            error="Failed to move all Virtual Machines",
            errorcb=errorcb,
        )
        return True
