from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor
from cloudbrokerlib.authenticator import auth
import requests
from urlparse import urlparse
from os import path as os_path
import yaml
import json
from cloudbrokerlib import resourcestatus


class cloudbroker_grid(BaseActor):
    def __init__(self):
        super(cloudbroker_grid, self).__init__()
        self.sysmodels = j.clients.osis.getNamespace("system")

    @auth(groups=["level1", "level2", "level3"])
    def purgeLogs(self, gid, age="-3d", **kwargs):
        return self.cb.executeJumpscript(
            "cloudscalers",
            "logs_purge",
            args={"age": age},
            gid=gid,
            role="master",
            wait=False,
        )["result"]

    @auth(groups=["level1", "level2", "level3"])
    def checkVMs(self, **kwargs):
        sessions = self.cb.agentcontroller.listSessions()
        for nodeid, roles in sessions.iteritems():
            if "master" in roles:
                gid = int(nodeid.split("_")[0])
                self.cb.executeJumpscript(
                    "jumpscale", "vms_check", gid=gid, role="master", wait=False
                )
        return "Scheduled check on VMS"

    @auth(groups=["level1", "level2", "level3"])
    def rename(self, name, gid, **kwargs):
        location = next(iter(self.models.location.search({"gid": gid})[1:]), None)
        if not location:
            raise exceptions.NotFound("Could not find location with gid %s" % gid)
        location["name"] = name
        self.models.location.set(location)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def add(self, name, gid, locationcode, **kwargs):
        location = next(iter(self.models.location.search({"gid": gid})[1:]), None)
        if location:
            raise exceptions.Conflict("Location with gid %s already exists" % gid)
        location = self.models.location.new()
        location.gid = gid
        location.flag = "black"
        location.locationCode = locationcode
        location.name = name
        self.models.location.set(location)
        return "Location has been added successfully, do not forget to add networkids and public IPs"

    @auth(groups=["level1", "level2", "level3"])
    def upgrade(self, url, **kwargs):
        manifest = requests.get(url).content
        version = os_path.splitext(os_path.basename(urlparse(url).path))[0]
        current_time = j.base.time.getTimeEpoch()

        jobinfo = self.cb.executeJumpscript(
            "greenitglobe",
            "execute_installer_command",
            role="controllernode",
            gid=j.application.whoAmI.gid,
            args={"cmd": "cluster pre-flight-check"},
        )

        if jobinfo["state"] == "OK":
            if jobinfo["result"]["return_code"]:
                raise exceptions.BadRequest(jobinfo["result"]["stderr"])
        else:
            raise exceptions.ServiceUnavailable("Can't connect to management node.")

        self.sysmodels.version.updateSearch(
            {"status": "INSTALLING"}, {"$set": {"status": "ERROR"}}
        )
        if self.sysmodels.version.count({"name": version}) > 0:
            self.sysmodels.version.updateSearch(
                {"name": version},
                {
                    "$set": {
                        "creationTime": current_time,
                        "status": "INSTALLING",
                        "url": url,
                        "manifest": manifest,
                    }
                },
            )
        else:
            versionmodel = self.sysmodels.version.new()
            versionmodel.name = version
            versionmodel.url = url
            versionmodel.manifest = manifest
            versionmodel.creationTime = current_time
            versionmodel.status = "INSTALLING"
            self.sysmodels.version.set(versionmodel)

        gids = [x["gid"] for x in self.models.location.search({"$fields": ["gid"]})[1:]]
        for gid in gids:
            self.cb.executeJumpscript(
                "greenitglobe",
                "delete_file",
                role="controllernode",
                gid=gid,
                wait=True,
                all=True,
                args={"path": "/var/ovc/updatelogs/update_env.log"},
            )
            self.cb.executeJumpscript(
                "greenitglobe",
                "upgrade_cluster",
                role="controllernode",
                gid=gid,
                wait=False,
            )
        return {"redirect_url": "/updating"}

    @auth(groups=["level1", "level2", "level3"], skipversioncheck=True)
    def runUpgradeScript(self, **kwargs):
        current_version_dict = self.sysmodels.version.searchOne(
            {"status": "INSTALLING"}
        )
        previous_version_dict = self.sysmodels.version.searchOne({"status": "PREVIOUS"})
        if previous_version_dict:
            previous_version = previous_version_dict["name"]
        else:
            previous_version = current_version_dict["name"]
        location_url = j.apps.cloudapi.locations.getUrl()
        job = self.cb.executeJumpscript(
            "greenitglobe",
            "upgrader",
            role="master",
            gid=j.application.whoAmI.gid,
            wait=True,
            args={
                "previous_version": previous_version,
                "current_version": current_version_dict["name"],
                "location_url": location_url,
            },
        )
        if job["state"] != "OK":
            raise exceptions.Error("Couldn't execute upgrade script")
        self.sysmodels.version.updateSearch(
            {"name": current_version_dict["name"]},
            {"$set": {"status": "CURRENT", "updateTime": j.base.time.getTimeEpoch()}},
        )
        return "Upgrade script ran successfully"

    @auth(groups=["level1", "level2", "level3"], skipversioncheck=True)
    def upgradeFailed(self, **kwargs):
        result = self.sysmodels.version.updateSearch(
            {"status": "INSTALLING"}, {"$set": {"status": "ERROR"}}
        )
        return bool(result["nModified"])

    @auth(groups=["level1", "level2", "level3"])
    def listVersions(self, status=None, **kwargs):
        query = dict()
        if status:
            query["status"] = status.upper()

        versions = self.sysmodels.version.search(query, size=0)[1:]
        return versions

    @auth(groups=["level1", "level2", "level3"])
    def deleteVersion(self, id, **kwargs):
        version = self.sysmodels.version.searchOne({"id": id, "status": "ERROR"})
        if not version:
            raise exceptions.NotFound(
                "Couldn't find version in state ERROR with id: {}".format(id)
            )

        result = self.sysmodels.version.deleteSearch({"id": id})
        return bool(result)

    @auth(groups=["level1", "level2", "level3"])
    def changeSettings(self, id, settings, **kwargs):
        if self.sysmodels.grid.count({"id": id}) == 0:
            raise exceptions.NotFound("No grid with id {} was found".format(id))
        try:
            settings = yaml.load(settings)
        except:
            raise exceptions.BadRequest("settings needs to be in valid YAML format")
        if not isinstance(settings, dict):
            raise exceptions.BadRequest(
                "settings needs to be in valid YAML format and needs to be an object"
            )
        rgst_data = settings.get("docker_registry")
        if not rgst_data:
            raise exceptions.BadRequest("Need to specify private docker registry data(docker_registry: username, password, server)")
        current_settings = self.sysmodels.grid.searchOne({"id": id})
        curr_rgst_data = current_settings.get("settings", {}).get("docker_registry", {})
        if rgst_data != curr_rgst_data:
            if "https:" in rgst_data["server"]:
                raise exceptions.BadRequest("Docker registry server shouldn't contain the server protocol")
            auth = requests.auth.HTTPBasicAuth(rgst_data["username"], rgst_data["password"])
            try:
                res = requests.get("https://{}/v2".format(rgst_data["server"]), auth=auth)
            except requests.ConnectionError:
                try:
                    res = requests.get("http://{}/v2".format(rgst_data["server"]), auth=auth)
                except requests.ConnectionError:
                    raise exceptions.BadRequest("Can't connect to specified registry server")
            if res.status_code == 401:
                header = res.headers.get('Www-Authenticate', '')
                if header.lower().startswith('bearer '):
                    parts = header[len('Bearer '):].split(",")
                    info = {}
                    for part in parts:
                        key, value = part.split("=", 1)
                        info[key] = value.strip('"')
                    if 'realm' in info:
                        realm = info.pop('realm')
                        res = requests.get(realm, params=info, auth=auth)
            if res.status_code != 200:
                raise exceptions.BadRequest("Docker registry credentials not valid")
            jobinfo = self.cb.executeJumpscript(
                "greenitglobe",
                "update_env_config",
                role="controllernode",
                gid=j.application.whoAmI.gid,
                args={"data": {"docker_registry": rgst_data}},
            )
            if jobinfo["state"] != "OK":
                raise exceptions.ServiceUnavailable("Couldn't update system config with docker registry data")
        self.sysmodels.grid.updateSearch({"id": id}, {"$set": {"settings": settings}})
        return "Changing settings done successfully"

    @auth(groups=["level2", "level3"])
    def executeMaintenanceScript(self, gid, nodestype, script, **kwargs):
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._executeMaintenanceScript,
            args=(int(gid), nodestype, script),
            kwargs=kwargs,
            title="Executing maintenance script",
            success="Maintenance Script executed successfully",
            error="Failed to execute maintenance script",
        )

    @auth(groups=["level1", "level2", "level3"])
    def _executeMaintenanceScript(self, gid, nodestype, script, **kwargs):
        if nodestype == "both":
            nodestype = ["cpunode", "storagenode"]
        else:
            nodestype = [nodestype]

        sessions = self.cb.agentcontroller.listSessions()
        for nodeid, roles in sessions.iteritems():
            node_actor = j.apps.cloudbroker.node
            nid = int(nodeid.split("_")[1])
            if int(nodeid.split("_")[0]) == gid:
                if set(roles) & set(
                    nodestype
                ):  # check of there is intersection between nodestype and roles
                    # put node in maintenance
                    node_actor.maintenance(nid, gid, "stop", **kwargs)
                    # execute the script via agentcontroller
                    node_actor.execute_script(nid, gid, script)
                    # enable it again
                    node_actor.enable(nid, gid, "Back from maintenance", **kwargs)
        return "Script Executed"

    @auth(groups=["level1", "level2", "level3"])
    def createSystemSpace(
        self,
        id,
        name,
        imageId,
        bootsize,
        dataDiskSize,
        sizeId=None,
        vcpus=None,
        memory=None,
        userdata=None,
        **kwargs
    ):
        try:
            grid = self.sysmodels.grid.get(id)
        except:
            raise exceptions.NotFound("No grid with id {} was found".format(id))
        all_vms = self.models.vmachine.search(
            {"status": {"$nin": resourcestatus.Machine.INVALID_STATES}}
        )[1:]
        vms = filter(
            lambda vm: self.models.disk.count({"id": {"$in": vm["disks"]}, "type": "P"})
            > 0,
            all_vms,
        )
        if vms:
            raise exceptions.BadRequest("System space already exists on this location")
        stacks_pdisks = []
        for stack in self.models.stack.search({"gid": id})[1:]:
            pdisks = []
            job = self.cb.executeJumpscript(
                "jumpscale",
                "exec",
                nid=stack["referenceId"],
                wait=True,
                args={"cmd": "lsblk -b -J"},
            )
            disks_info = json.loads(job["result"][1])
            for disk_info in disks_info["blockdevices"]:
                if not disk_info.get("children") and not disk_info["mountpoint"]:
                    pdisks.append(disk_info)
            if pdisks:
                stacks_pdisks.append((stack, pdisks))

        if not stacks_pdisks:
            return "Can't create system space on this location: {}. No physical disks available on compute nodes".format(
                id
            )

        username = kwargs["ctx"].env["beaker.session"]["user"]
        accountId = j.apps.cloudbroker.account.create(
            name=name, username=username, emailaddress=None
        )
        cloudspaceId = j.apps.cloudapi.cloudspaces.create(
            accountId=accountId,
            location=grid.name,
            name=name,
            access=username,
            ctx=kwargs["ctx"],
        )
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        for stack, pdisks in stacks_pdisks:
            pvolumes = []
            diskids = []
            for order, disk_info in enumerate(pdisks):
                size = j.tools.units.bytes.toSize(int(disk_info["size"]), output="G")
                disk, volume = j.apps.cloudapi.disks._create(
                    accountId=accountId,
                    gid=id,
                    name="pdisk %s" % str(order + 1),
                    description="Physical disk",
                    size=int(size),
                    type="P",
                    physicalSource="/dev/%s" % disk_info["name"],
                    nid=stack["referenceId"],
                    order=order + 2,
                )

                diskids.append(disk.id)
                pvolumes.append(volume)
            machine, vmauth, volumes = self.cb.machine.createModel(
                name="System machine %s" % stack["id"],
                description="System space machine",
                cloudspace=cloudspace,
                imageId=imageId,
                sizeId=sizeId,
                disksize=bootsize,
                datadisks=[dataDiskSize],
                vcpus=vcpus,
                memory=memory,
            )
            volumes += pvolumes
            machine.disks += diskids
            self.models.vmachine.set(machine)
            self.cb.machine.create(
                machine, vmauth, cloudspace, volumes, imageId, stack["id"], userdata
            )
        return "System space successfully created"

    def status(self, **kwargs):
        if self.sysmodels.version.count({"status": "INSTALLING"}) > 0:
            raise exceptions.ServiceUnavailable("Currently being upgraded")
        else:
            return True
