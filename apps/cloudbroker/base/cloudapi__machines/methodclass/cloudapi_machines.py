from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import authenticator, network, resourcestatus
from cloudbrokerlib.baseactor import BaseActor
from CloudscalerLibcloud.utils import ovf
import time
import itertools
import re
import requests
import gevent
import urlparse
import math
from datetime import datetime


class RequireState(object):
    def __init__(self, state, msg):
        self.state = state
        self.msg = msg

    def __call__(self, func):
        def wrapper(s, **kwargs):
            machineId = int(kwargs["machineId"])
            if not s.models.vmachine.exists(machineId):
                raise exceptions.NotFound(
                    "Machine with id %s was not found" % machineId
                )

            machine = s.get(machineId)
            if not machine["status"] == self.state:
                raise exceptions.Conflict(self.msg)
            return func(s, **kwargs)

        return wrapper


class cloudapi_machines(BaseActor):
    """
    API Actor api, this actor is the final api a enduser uses to manage his resources

    """

    def __init__(self):
        super(cloudapi_machines, self).__init__()
        self.network = network.Network(self.models)
        self.netmgr = self.cb.netmgr
        self.acl = self.cb.agentcontroller

    def _action(
        self, machineId, actiontype, newstatus=None, provider=None, node=None, **kwargs
    ):
        """
        Perform a action on a machine, supported types are STOP, START, PAUSE, RESUME, REBOOT
        param:machineId id of the machine
        param:actiontype type of the action(e.g stop, start, ...)
        result bool

        """
        with self.models.vmachine.lock(machineId):
            if provider is None or node is None:
                provider, node, machine = self.cb.getProviderAndNode(machineId)
            else:
                machine = self.models.vmachine.get(machineId)
            if machine.type != "VIRTUAL":
                raise exceptions.BadRequest(
                    "Action %s is not support on machine %s" % (actiontype, machineId)
                )
            if node.extra.get("locked", False):
                raise exceptions.Conflict("Can not %s a locked Machine" % actiontype)
            node.extra.update({"machineId": machineId})
            actionname = "%s_node" % actiontype.lower()
            method = getattr(provider, actionname, None)
            if not method:
                method = getattr(provider, "ex_%s" % actionname.lower(), None)
                if not method:
                    raise exceptions.BadRequest(
                        "Action %s is not support on machine %s"
                        % (actiontype, machineId)
                    )
            result = method(node, **kwargs)
            if newstatus and newstatus != machine.status:
                update = {"status": newstatus, "updateTime": int(time.time())}
                self.models.vmachine.updateSearch({"id": machine.id}, {"$set": update})
            return result

    def _get_boot_disk(self, machine):
        bootdisk = None
        for disk_id in machine.disks:
            disk = self.models.disk.get(disk_id)
            if disk.type == "B" and bootdisk:
                raise exceptions.BadRequest("Machine has more than one boot disk")
            if disk.type == "B":
                bootdisk = disk
        return bootdisk

    @authenticator.auth(acl={"machine": set("X")})
    def start(self, machineId, diskId=None, **kwargs):
        """
        Start the machine

        :param machineId: id of the machine
        """
        machine = self._getMachine(machineId)
        bootdisk = self._get_boot_disk(machine)
        if not bootdisk:
            raise exceptions.BadRequest("This machine doesn't have a boot disk")
        if "start" in machine.tags.split(" "):
            j.apps.cloudbroker.machine.untag(machineId=machine.id, tagName="start")
        if machine.status not in resourcestatus.Machine.UP_STATES:
            self.cb.chooseStack(machine)
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        tags = j.core.tags.getObject(machine.tags)
        if diskId is not None:
            if not self.models.disk.exists(diskId):
                raise exceptions.BadRequest(
                    "Rescue disk with id {} does not exist".format(diskId)
                )
            for volume in node.extra["volumes"][:]:
                if volume.type == "cdrom":
                    node.extra["volumes"].remove(volume)
            disk = self.models.disk.get(diskId)
            if disk.type != "C":
                raise exceptions.BadRequest("diskId is not of type CD-ROM")
            if disk.status in resourcestatus.Image.INVALID_STATES:
                raise exceptions.BadRequest(
                    "Rescue disk with id {} is not available".format(diskId)
                )
            cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
            if disk.accountId and disk.accountId != cloudspace.accountId:
                raise exceptions.BadRequest(
                    "Rescue disk with id {} belongs to another account".format(diskId)
                )
            volume = j.apps.cloudapi.disks.getStorageVolume(disk, provider, node)
            node.extra["volumes"].append(volume)
            node.extra["bootdev"] = "cdrom"
            tags.tagSet("cdrom", disk.id)
            self.models.vmachine.updateSearch(
                {"id": machine.id}, {"$set": {"tags": tags.tagstring}}
            )
        elif "cdrom" in tags.tags:
            tags.tagDelete("cdrom")
            self.models.vmachine.updateSearch(
                {"id": machine.id}, {"$set": {"tags": tags.tagstring}}
            )

        return self._action(
            machineId,
            "start",
            resourcestatus.Machine.RUNNING,
            provider=provider,
            node=node,
        )

    @authenticator.auth(acl={"machine": set("X")})
    def stop(self, machineId, force=False, **kwargs):
        """
        Stop the machine

        :param machineId: id of the machine
        """
        machine = self._getMachine(machineId)
        tags = j.core.tags.getObject(machine.tags)
        if "cdrom" in tags.tags:
            tags.tagDelete("cdrom")
            self.models.vmachine.updateSearch(
                {"id": machine.id}, {"$set": {"tags": tags.tagstring}}
            )
        return self._action(
            machineId, "stop", resourcestatus.Machine.HALTED, force=force
        )

    @authenticator.auth(acl={"machine": set("X")})
    def reboot(self, machineId, **kwargs):
        """
        Reboot the machine

        :param machineId: id of the machine
        """
        return self._action(machineId, "soft_reboot", resourcestatus.Machine.RUNNING)

    @authenticator.auth(acl={"machine": set("X")})
    def reset(self, machineId, **kwargs):
        """
        Reset the machine, force reboot

        :param machineId: id of the machine
        """
        return self._action(machineId, "hard_reboot", resourcestatus.Machine.RUNNING)

    @authenticator.auth(acl={"machine": set("X")})
    def pause(self, machineId, **kwargs):
        """
        Pause the machine

        :param machineId: id of the machine
        """
        return self._action(machineId, "pause", resourcestatus.Machine.PAUSED)

    @authenticator.auth(acl={"machine": set("X")})
    def resume(self, machineId, **kwargs):
        """
        Resume the machine

        :param machineId: id of the machine
        """
        return self._action(machineId, "resume", resourcestatus.Machine.RUNNING)

    @authenticator.auth(acl={"cloudspace": set("C")})
    def addDisk(
        self,
        machineId,
        diskName,
        description,
        size=10,
        type="D",
        ssdSize=0,
        iops=2000,
        **kwargs
    ):
        """
        Create and attach a disk to the machine

        :param machineId: id of the machine
        :param diskName: name of disk
        :param description: optional description
        :param size: size in GByte default=10
        :param type: (B;D;T)  B=Boot;D=Data;T=Temp default=B
        :return int, id of the disk

        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        if len(machine.disks) >= 25:
            raise exceptions.BadRequest("Cannot create more than 25 disk on a machine")
        if type == "B":
            raise exceptions.BadRequest("Cannot create boot disks")
        cloudspace = self.models.cloudspace.get(machine.cloudspaceId)

        with self.models.account.lock(cloudspace.accountId):
            # Validate that enough resources are available in the CU limits to add the disk
            j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
                cloudspace.id, vdisksize=size
            )
            disk, _ = j.apps.cloudapi.disks._create(
                accountId=cloudspace.accountId,
                gid=cloudspace.gid,
                name=diskName,
                description=description,
                size=size,
                type=type,
                iops=iops,
                **kwargs
            )
        self._attach_disk_volume(machine, node, disk, provider)
        return disk.id

    @authenticator.auth(acl={"cloudspace": set("X")})
    def detachDisk(self, machineId, diskId, **kwargs):
        """
        Detach a disk from the machine

        :param machineId: id of the machine
        :param diskId: id of disk to detach
        :return: True if disk was detached successfully
        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        diskId = int(diskId)
        if diskId not in machine.disks:
            return True
        disk = self.models.disk.get(int(diskId))
        if disk.type == "B":
            raise exceptions.BadRequest("Cannot detach boot disks")
        volume = j.apps.cloudapi.disks.getStorageVolume(disk, provider, node)
        provider.detach_volume(volume)
        machine.disks.remove(diskId)
        disk.status = resourcestatus.Disk.CREATED
        self.models.disk.set(disk)
        self.models.vmachine.set(machine)
        return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def attachDisk(self, machineId, diskId, **kwargs):
        """
        Attach a disk to the machine

        :param machineId: id of the machine
        :param diskId: id of disk to attach
        :return: True if disk was attached successfully
        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        diskId = int(diskId)
        if diskId in machine.disks:
            return True
        if len(machine.disks) >= 25:
            raise exceptions.BadRequest("Cannot attach more than 25 disk to a machine")
        disk = self.models.disk.get(int(diskId))
        if disk.type == "B":
            raise exceptions.BadRequest("Cannot attach boot disks")
        cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
        if disk.accountId != cloudspace.accountId:
            raise exceptions.Forbidden("This disk belongs to another account")

        count = self.models.vmachine.count({"disks": diskId})
        if count > 0:
            raise exceptions.BadRequest(
                "This disk is already attached to another machine"
            )
        # the disk was not attached to any machines so check if there is enough resources in the cloudspace
        j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
            machine.cloudspaceId, vdisksize=disk.sizeMax, checkaccount=False
        )
        return self._attach_disk_volume(machine, node, disk, provider)

    def _attach_disk_volume(self, machine, node, disk, provider):
        diskorder = 1
        query = {"$query": {"id": {"$in": machine.disks}}, "$fields": ["order"]}
        diskorders = [vmdisk["order"] for vmdisk in self.models.disk.search(query)[1:]]
        while diskorder in diskorders:
            diskorder += 1

        disk.order = diskorder
        volume = j.apps.cloudapi.disks.getStorageVolume(disk, provider, node)
        provider.attach_volume(node, volume)
        self.models.disk.updateSearch({"id": disk.id}, {"$set": {"order": diskorder}})
        machine.disks.append(disk.id)
        disk.status = resourcestatus.Disk.ASSIGNED
        self.models.disk.set(disk)
        self.models.vmachine.set(machine)
        return True

    @authenticator.auth(acl={"account": set("C")})
    @RequireState(
        resourcestatus.Machine.HALTED,
        "A template can only be created for a stopped Machine",
    )
    def createTemplate(self, machineId, templateName, callbackUrl, **kwargs):
        """
        Create a template from a machine
        param:machineId id of the machine to export
        param:templateName name of the template to be created
        param:callbackUrl callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion.
        """
        gevent.spawn(
            self.syncCreateTemplate, machineId, templateName, callbackUrl, **kwargs
        )
        return True

    def syncCreateTemplate(self, machineId, templateName, callbackUrl, **kwargs):
        """
        Create a template from the active machine

        :param machineId: id of the machine
        :param templatename: name of the template
        :param basename: snapshot id on which the template is based
        :return True if template was created
        """
        machine = self._getMachine(machineId)
        origimage = self.models.image.get(machine.imageId)
        ctx = kwargs["ctx"]
        user = ctx.env["beaker.session"]["user"]
        userobj = j.core.portal.active.auth.getUserInfo(user)
        provider, node, _ = self.cb.getProviderAndNode(machineId)
        firstdisk = self.models.disk.get(machine.disks[0])
        cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
        image = self.models.image.new()
        image.name = templateName
        image.type = "Custom Templates"
        image.username = machine.accounts[0].login
        image.password = machine.accounts[0].password
        image.size = firstdisk.sizeMax
        image.accountId = cloudspace.accountId
        image.status = "CREATING"
        image.gid = cloudspace.gid
        image.bootType = origimage.bootType
        image.hotResize = origimage.hotResize
        image.provider_name = origimage.provider_name
        imageid = self.models.image.set(image)[0]
        image.id = imageid
        try:
            volume = provider.create_volume(
                image.size,
                "templates/{}_{}".format(machineId, templateName),
                vpool="vmstor",
                type="C"
            )
            image_path = provider.ex_create_template(
                node, templateName, volume.vdiskguid
            )
        except Exception as e:
            image = self.models.image.get(imageid)
            if image.status == "CREATING":
                image.status = "ERROR"
                self.models.image.set(image)
            eco = j.errorconditionhandler.processPythonExceptionObject(e)
            eco.process()
            if not callbackUrl:
                [
                    self._sendCreateTemplateCompletionMail(
                        node.name, email, success=False, eco=eco.guid
                    )
                    for email in userobj.emails
                ]
            else:
                requests.get(callbackUrl)
            raise
        image.UNCPath = image_path
        image.referenceId = volume.vdiskguid
        image.status = "CREATED"
        self.models.image.set(image)
        self.models.stack.updateSearch(
            {"gid": cloudspace.gid}, {"$addToSet": {"images": imageid}}
        )
        if not callbackUrl:
            [
                self._sendCreateTemplateCompletionMail(node.name, email, success=True)
                for email in userobj.emails
            ]
        else:
            requests.get(callbackUrl)

        return imageid

    def _sendImportCompletionMail(
        self, name, emailaddress, link, success=True, error=False
    ):
        fromaddr = self.hrd.get("instance.openvcloud.supportemail")
        if isinstance(emailaddress, list):
            toaddrs = emailaddress
        else:
            toaddrs = [emailaddress]

        success = "successfully" if success else "not successfully"
        args = {
            "error": error,
            "success": success,
            "email": emailaddress,
            "link": link,
            "name": name,
        }

        message = j.core.portal.active.templates.render(
            "cloudbroker/email/users/import_completion.html", **args
        )
        subject = j.core.portal.active.templates.render(
            "cloudbroker/email/users/import_completion.subject.txt", **args
        )

        j.clients.email.send(toaddrs, fromaddr, subject, message, files=None)

    def _sendExportCompletionMail(self, name, emailaddress, success=True, error=False):
        fromaddr = self.hrd.get("instance.openvcloud.supportemail")
        if isinstance(emailaddress, list):
            toaddrs = emailaddress
        else:
            toaddrs = [emailaddress]

        success = "successfully" if success else "not successfully"
        args = {"error": error, "success": success, "email": emailaddress, "name": name}

        message = j.core.portal.active.templates.render(
            "cloudbroker/email/users/export_completion.html", **args
        )
        subject = j.core.portal.active.templates.render(
            "cloudbroker/email/users/export_completion.subject.txt", **args
        )

        j.clients.email.send(toaddrs, fromaddr, subject, message, files=None)

    def _sendCreateTemplateCompletionMail(
        self, name, emailaddress, success=True, error=False, eco=""
    ):
        fromaddr = self.hrd.get("instance.openvcloud.supportemail")
        if isinstance(emailaddress, list):
            toaddrs = emailaddress
        else:
            toaddrs = [emailaddress]

        success = "successfully" if success else "not successfully"
        args = {
            "error": error,
            "success": success,
            "email": emailaddress,
            "name": name,
            "eco": eco,
        }

        subject = j.core.portal.active.templates.render(
            "cloudbroker/email/users/template_creation_subject.txt", **args
        )
        message = j.core.portal.active.templates.render(
            "cloudbroker/email/users/template_creation_completion.html", **args
        )

        j.clients.email.send(toaddrs, fromaddr, subject, message, files=None)

    def syncImportOVF(
        self,
        uploaddata,
        envelope,
        cloudspace,
        name,
        description,
        callbackUrl,
        user,
        vcpus=None,
        memory=None,
        sizeId=None,
        ctx=None,
    ):
        try:
            error = False
            userobj = j.core.portal.active.auth.getUserInfo(user)

            vm = self.models.vmachine.new()
            vm.cloudspaceId = cloudspace.id

            machine = ovf.ovf_to_model(envelope)

            vm.name = name
            vm.descr = description
            if sizeId and (vcpus or memory):
                raise exceptions.BadRequest(
                    "sizeId and (vcpus or memory) are mutually exclusive"
                )
            # make sure that if u pass memory or vcpus u have to pass the other as well
            if (memory or vcpus) and not (memory and vcpus):
                raise exceptions.BadRequest(
                    "cannot pass vcpus or memory without the other."
                )
            if sizeId == -1:
                sizeId = None
            if sizeId:
                size = self.models.size.get(sizeId)
                vm.sizeId = sizeId
                memory = size.memory
                vcpus = size.vcpus
            vm.memory = memory
            vm.vcpus = vcpus
            vm.imageId = j.apps.cloudapi.images.get_or_create_by_name(
                "Imported Machine"
            ).id
            vm.creationTime = int(time.time())
            vm.updateTime = int(time.time())
            vm.type = "VIRTUAL"

            totaldisksize = 0
            bootdisk = None
            for i, diskobj in enumerate(machine["disks"]):
                disk = self.models.disk.new()
                disk.gid = cloudspace.gid
                disk.order = i
                disk.accountId = cloudspace.accountId
                disk.type = "B" if i == 0 else "D"
                disk.sizeMax = int(math.ceil(diskobj["size"] / 1024. ** 3))
                totaldisksize += disk.sizeMax
                disk.name = diskobj["name"]
                diskid = self.models.disk.set(disk)[0]
                if i == 0:
                    bootdisk = disk
                vm.disks.append(diskid)
                diskobj["id"] = diskid
                diskobj["path"] = "disk-%i.vmdk" % i
            # Validate that enough resources are available in the CU limits to clone the machine
            size = {"memory": memory, "vcpus": vcpus}
            j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
                cloudspace.id, vcpus, memory / 1024.0, totaldisksize
            )

            vm.id = self.models.vmachine.set(vm)[0]
            stack = self.cb.getBestStack(cloudspace.gid, vm.imageId, memory=memory)
            provider = self.cb.getProviderByStackId(stack["id"])

            machine["id"] = vm.id

            # the disk objects in the machine gets changed in the jumpscript and a guid is added to them
            jobargs = uploaddata.copy()
            jobargs["machine"] = machine
            machine = self.acl.execute(
                "greenitglobe",
                "cloudbroker_import",
                gid=cloudspace.gid,
                role="storagedriver",
                timeout=3600,
                args=jobargs,
            )
            try:
                provider.ex_extend_disk(machine["disks"][0]["guid"], bootdisk.sizeMax)
                node = provider.ex_import(
                    size, vm.id, cloudspace.networkId, machine["disks"]
                )
                stack_model = self.models.stack.new()
                stack_model.load(stack)
                self.cb.machine.updateMachineFromNode(vm, node, stack_model)
            except:
                self.cb.machine.cleanup(vm)
                raise
            gevent.spawn(
                self.cb.cloudspace.update_firewall,
                cloudspace,
                ctx=j.core.portal.active.requestContext,
            )
            if not callbackUrl:
                url = j.apps.cloudapi.locations.getUrl() + "/g8vdc/#/edit/%s" % vm.id
                [
                    self._sendImportCompletionMail(name, email, url, success=True)
                    for email in userobj.emails
                ]
            else:
                requests.get(callbackUrl)
        except Exception as e:
            eco = j.errorconditionhandler.processPythonExceptionObject(e)
            eco.process()
            error = True
            if not callbackUrl:
                [
                    self._sendImportCompletionMail(
                        name, email, "", success=False, error=error
                    )
                    for email in userobj.emails
                ]
            else:
                requests.get(callbackUrl)

    def syncExportOVF(
        self, uploaddata, vm, provider, cloudspace, user, callbackUrl, ctx=None
    ):
        try:
            error = False
            diskmapping = list()
            userobj = j.core.portal.active.auth.getUserInfo(user)
            disks = self.models.disk.search(
                {"id": {"$in": vm.disks}, "type": {"$ne": "M"}}
            )[1:]

            disks_snapshots = self.snapshot(
                vm.id, "export_%s" % (str(datetime.now())), force=True
            )

            try:
                volumes = []
                for disk in disks:
                    diskguid = disk["referenceId"].split("@")[1]
                    diskmapping = (
                        j.apps.cloudapi.disks.getStorageVolume(disk, provider),
                        "export/clonefordisk_%s" % diskguid,
                    )
                    volume = provider.ex_clone_disks([diskmapping], disks_snapshots)
                    volumes.append(volume[0])

                disknames = [volume.id.split("@")[0] for volume in volumes]
                osname = self.models.image.get(vm.imageId).name
                os = re.match("^[a-zA-Z]+", osname).group(0).lower()
                envelope = ovf.model_to_ovf(
                    {
                        "name": vm.name,
                        "description": vm.descr,
                        "cpus": vm.vcpus,
                        "mem": vm.memory,
                        "os": os,
                        "osname": osname,
                        "disks": [
                            {
                                "name": "disk-%i.vmdk" % i,
                                "size": disk["sizeMax"] * 1024 * 1024 * 1024,
                            }
                            for i, disk in enumerate(disks)
                        ],
                    }
                )
                jobargs = uploaddata.copy()
                jobargs.update({"envelope": envelope, "disks": disknames})

                export_job = self.acl.executeJumpscript(
                    "greenitglobe",
                    "cloudbroker_export",
                    gid=cloudspace.gid,
                    role="storagedriver",
                    timeout=3600,
                    args=jobargs,
                )
            finally:
                diskguids = [volume.vdiskguid for volume in volumes]
                provider.destroy_volumes_by_guid(diskguids)
            # TODO: the url to be sent to the user
            if export_job["state"] == "ERROR":
                raise exceptions.Error("Failed to export Virtual Machine")
            if not callbackUrl:
                [
                    self._sendExportCompletionMail(vm.name, email, success=True)
                    for email in userobj.emails
                ]
            else:
                requests.get(callbackUrl)
        except BaseException as e:
            eco = j.errorconditionhandler.processPythonExceptionObject(e)
            eco.process()
            error = True
            if not callbackUrl:
                [
                    self._sendExportCompletionMail(
                        vm.name, email, success=False, error=error
                    )
                    for email in userobj.emails
                ]
            else:
                requests.get(callbackUrl)
            raise

    def _validate_links(self, **kwargs):
        """
        Validate link & callbackUrl arguments to be proper https links to prevent SSRF attacks
        """
        for name, url in kwargs.iteritems():
            parsed = urlparse.urlparse(url)
            if not url:
                raise exceptions.BadRequest(
                    "{} parameter should not be empty".format(name)
                )
            if parsed.scheme != "https":
                raise exceptions.BadRequest(
                    "{} parameter only supports https links".format(name)
                )
            if ":" in parsed.netloc or "@" in parsed.netloc:
                raise exceptions.BadRequest(
                    "Non standard ports or embedded authentication is not supported for the {} parameter".format(
                        name
                    )
                )
            if ".." in parsed.path:
                raise exceptions.BadRequest(
                    "'..' character sequence is not supported in the {} parameter".format(
                        name
                    )
                )
            if "." not in parsed.netloc:
                raise exceptions.BadRequest(
                    "Local hostnames are not supported in the {} parameter".format(name)
                )

    @authenticator.auth(acl={"cloudspace": set("C")})
    def importOVF(
        self,
        link,
        username,
        passwd,
        path,
        cloudspaceId,
        name,
        description,
        callbackUrl,
        vcpus=None,
        memory=None,
        sizeId=None,
        **kwargs
    ):
        """
        Import a machine from owncloud(ovf)
        param:link WebDav link to owncloud
        param:username WebDav Username
        param:passwd WebDav Password
        param:path Path to ovf file in WebDav share
        param:cloudspaceId id of the cloudspace in which the vm should be created
        param:name name of machine
        param:description optional description
        param:sizeId the size id of the machine
        param:callbackUrl callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion.
        """
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        if cloudspace.status in resourcestatus.Cloudspace.INVALID_STATES:
            raise exceptions.BadRequest(
                "Can not import machine on a deleted Cloud Space"
            )
        self._validate_links(link=link)
        if callbackUrl is not None:
            self._validate_links(callbackUrl=callbackUrl)
        ctx = kwargs["ctx"]
        user = ctx.env["beaker.session"]["user"]
        uploaddata = {
            "link": link,
            "passwd": passwd,
            "path": path,
            "username": username,
        }
        job = self.acl.executeJumpscript(
            "greenitglobe",
            "cloudbroker_getenvelope",
            gid=cloudspace.gid,
            role="storagedriver",
            args=uploaddata,
        )
        if job["state"] == "ERROR":
            import json

            try:
                msg = json.loads(job["result"]["exceptioninfo"])["message"]
            except:
                msg = "Failed to retreive envelope"
            raise exceptions.BadRequest(msg)

        if sizeId and (vcpus or memory):
            raise exceptions.BadRequest(
                "sizeId and (vcpus or memory) are mutually exclusive"
            )
        if (memory or vcpus) and not (memory and vcpus):
            raise exceptions.BadRequest(
                "cannot pass vcpus or memory without the other."
            )

        gevent.spawn(
            self.syncImportOVF,
            uploaddata,
            job["result"],
            cloudspace,
            name,
            description,
            callbackUrl,
            user,
            vcpus,
            memory,
            sizeId,
            ctx=ctx,
        )

    @authenticator.auth(acl={"machine": set("X")})
    def exportOVF(self, link, username, passwd, path, machineId, callbackUrl, **kwargs):
        """
        Export a machine with it's disks to owncloud(ovf)
        param:link WebDav link to owncloud
        param:username WebDav Username
        param:passwd WebDav Password
        param:path Path to ovf file in WebDav share
        param:machineId id of the machine to export
        param:callbackUrl callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion.
        """
        provider, _, vm = self.cb.getProviderAndNode(machineId)
        if self.models.disk.count({"id": {"$in": vm.disks}, "type": "P"}) > 0:
            raise exceptions.BadRequest(
                "Can't export a vm with physical disks attached"
            )
        self._validate_links(link=link)
        if callbackUrl is not None:
            self._validate_links(callbackUrl=callbackUrl)
        ctx = kwargs["ctx"]
        user = ctx.env["beaker.session"]["user"]
        cloudspace = self.models.cloudspace.get(vm.cloudspaceId)
        uploaddata = {
            "link": link,
            "passwd": passwd,
            "path": path,
            "username": username,
        }
        job = self.acl.executeJumpscript(
            "greenitglobe",
            "cloudbroker_export_readme",
            gid=cloudspace.gid,
            role="storagedriver",
            timeout=3600,
            args=uploaddata,
        )
        if job["state"] == "ERROR":
            import json

            try:
                msg = json.loads(job["result"]["exceptioninfo"])["message"]
            except:
                msg = "Failed to upload to link"
            raise exceptions.BadRequest(msg)
        gevent.spawn(
            self.syncExportOVF,
            uploaddata,
            vm,
            provider,
            cloudspace,
            user,
            callbackUrl,
            ctx=j.core.portal.active.requestContext,
        )
        return True

    @authenticator.auth(acl={"machine": set("X")})
    def backup(self, machineId, backupName, **kwargs):
        """
        backup is in fact an export of the machine to a cloud system close to the IAAS system on which the machine is running
        param:machineId id of machine to backup
        param:backupName name of backup
        result int

        """
        storageparameters = {
            "storage_type": "ceph",
            "bucket": "vmbackup",
            "mdbucketname": "mdvmbackup",
        }

        return self._export(machineId, backupName, storageparameters)

    @authenticator.auth(acl={"cloudspace": set("C")})
    def create(
        self,
        cloudspaceId,
        name,
        description,
        imageId,
        disksize,
        datadisks,
        sizeId=None,
        userdata=None,
        vcpus=None,
        memory=None,
        **kwargs
    ):
        """
        Create a machine based on the available sizes, in a certain cloud space
        The user needs write access rights on the cloud space

        :param cloudspaceId: id of cloud space in which we want to create a machine
        :param name: name of machine
        :param description: optional description
        :param sizeId: id of the specific size
        :param imageId: id of the specific image
        :param disksize: size of base volume
        :param datadisks: list of extra data disks
        :param vcpu: int number of cpu to assign to machine 
        :param memory: int amount of memory to assign to machine
        :return bool

        """
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        with self.models.account.lock(cloudspace.accountId):
            machine, auth, volumes, cloudspace = self._prepare_machine(
                cloudspaceId,
                name,
                description,
                imageId,
                disksize,
                datadisks,
                sizeId,
                vcpus,
                memory,
                userdata,
            )

        machineId = self.cb.machine.create(
            machine, auth, cloudspace, volumes, imageId, None, userdata
        )
        kwargs["ctx"].env["tags"] += " machineId:{}".format(machineId)
        gevent.spawn(
            self.cb.cloudspace.update_firewall,
            cloudspace,
            ctx=j.core.portal.active.requestContext,
        )
        return machineId

    def _prepare_machine(
        self,
        cloudspaceId,
        name,
        description,
        imageId,
        disksize,
        datadisks,
        sizeId=None,
        vcpus=None,
        memory=None,
        userdata=None,
        **kwargs
    ):
        """
        internal method to prevent code duplication
        """
        if sizeId and (vcpus or memory):
            raise exceptions.BadRequest(
                "sizeId and (vcpus or memory) are mutually exclusive"
            )
        # make sure that if u pass memory or vcpus u have to pass the other as well
        if not sizeId and not (memory and vcpus):
            raise exceptions.BadRequest(
                "If sizeId is not specified need to specify both memory and vcpus."
            )
        datadisks = datadisks or []
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        self.cb.machine.validateCreate(
            cloudspace, name, sizeId, imageId, disksize, datadisks, userdata
        )
        # Validate that enough resources are available in the CU limits to create the machine
        if sizeId:
            size = self.models.size.get(sizeId)
            memory = size.memory
            vcpus = size.vcpus
        totaldisksize = sum(datadisks + [disksize])

        if memory % 2:
            raise exceptions.BadRequest("memory value should be an even number")

        j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
            cloudspace.id, vcpus, memory / 1024.0, totaldisksize
        )
        machine, auth, volumes = self.cb.machine.createModel(
            name,
            description,
            cloudspace,
            imageId,
            sizeId,
            disksize,
            datadisks,
            vcpus,
            memory,
        )
        return machine, auth, volumes, cloudspace

    @authenticator.auth(acl={"cloudspace": set("X")})
    def delete(self, machineId, permanently=False, **kwargs):
        """
        Delete the machine

        :param machineId: id of the machine
        :param permanently: whether to completely remove the machine or not
        :return True if machine was deleted successfully

        """
        provider, node, vmachinemodel = self.cb.getProviderAndNode(machineId)
        if "name" in kwargs and kwargs["name"]:
            if vmachinemodel.name != kwargs["name"]:
                raise exceptions.BadRequest("Incorrect machine name specified")
        if node and node.extra.get("locked", False):
            raise exceptions.Conflict("Can not delete a locked Machine")
        current_status = vmachinemodel.status
        if current_status == resourcestatus.Machine.DELETED:
            if permanently:
                self.cb.machine.destroy_machine(machineId)
            return True
        vms = self.models.vmachine.search(
            {
                "cloneReference": machineId,
                "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
            }
        )[1:]
        if vms:
            clonenames = ["  * %s" % vm["name"] for vm in vms]
            raise exceptions.Conflict(
                "Can not delete a Virtual Machine which has clones.\nExisting Clones Are:\n%s"
                % "\n".join(clonenames)
            )
        vmachinemodel.nics = self._detachExternalNetworkFromModel(vmachinemodel.nics)
        self.models.vmachine.set(vmachinemodel)
        delete_state = resourcestatus.Machine.DELETED
        pdisks = self.models.disk.search(
            {"id": {"$in": vmachinemodel.disks}, "type": "P"}
        )[1:]
        if pdisks or permanently:
            delete_state = resourcestatus.Machine.DESTROYED
        if not current_status == delete_state:
            current_time = int(time.time())
            vmachinemodel.updateTime = current_time
            vmachinemodel.deletionTime = current_time
            vmachinemodel.status = delete_state
            self.models.vmachine.set(vmachinemodel)

        try:
            j.apps.cloudapi.portforwarding.deleteByVM(vmachinemodel)
        except Exception as e:
            j.errorconditionhandler.processPythonExceptionObject(
                e,
                message="Failed to delete portforwardings for vm with id %s"
                % machineId,
            )
        except exceptions.BaseError as berror:
            j.errorconditionhandler.processPythonExceptionObject(
                berror,
                message="Failed to delete pf for vm with id %s can not apply config"
                % machineId,
            )
        if provider:
            provider.destroy_node(node)
        self.models.disk.updateSearch(
            {"id": {"$in": vmachinemodel.disks}},
            {"$set": {"status": resourcestatus.Disk.DELETED}},
        )

        # delete leases
        cloudspace = self.models.cloudspace.get(vmachinemodel.cloudspaceId)
        fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
        macs = list()
        for nic in vmachinemodel.nics:
            if nic.type != "PUBLIC" and nic.macAddress:
                macs.append(nic.macAddress)
        if macs:
            try:
                self.netmgr.fw_remove_lease(fwid, macs)
            except exceptions.ServiceUnavailable as e:
                j.errorconditionhandler.processPythonExceptionObject(
                    e, message="vfw is not deployed yet"
                )
        for pdisk in pdisks:
            disk_info = urlparse.urlparse(pdisk["referenceId"])
            node_id = disk_info.query.split("=")[1]
            cmd = "dd if=/dev/zero bs=1M count=500 of={}".format(disk_info.path)
            self.acl.executeJumpscript(
                "jumpscale", "exec", nid=node_id, args={"cmd": cmd}
            )
        if delete_state == resourcestatus.Machine.DESTROYED:
            self.cb.machine.destroy_volumes(vmachinemodel.disks)
        return True

    @authenticator.auth(acl={"machine": set("R")})
    def get(self, machineId, **kwargs):
        """
        Get information from a certain object.
        This contains all information about the machine.
        param:machineId id of machine
        result

        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        if machine.status in resourcestatus.Machine.INVALID_STATES:
            raise exceptions.NotFound("Machine %s not found" % machineId)
        locked = False
        diskquery = {"id": {"$in": machine.disks}}
        disks = self.models.disk.search(
            {
                "$query": diskquery,
                "$fields": ["status", "type", "name", "descr", "acl", "sizeMax", "id"],
            }
        )[1:]
        storage = sum(disk["sizeMax"] for disk in disks)
        osImage = self.models.image.get(machine.imageId).name
        if machine.nics and machine.nics[0].ipAddress == "Undefined" and node:
            if node.private_ips:
                machine.nics[0].ipAddress = node.private_ips[0]
            else:
                cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
                fwid = "%s_%s" % (cloudspace.gid, cloudspace.networkId)
                try:
                    ipaddress = self.netmgr.fw_get_ipaddress(
                        fwid, machine.nics[0].macAddress
                    )
                    if ipaddress:
                        machine.nics[0].ipAddress = ipaddress
                        self.models.vmachine.set(machine)
                except exceptions.ServiceUnavailable:
                    pass  # VFW not deployed yet
        if node:
            locked = node.extra.get("locked", False)

        updateTime = machine.updateTime if machine.updateTime else None
        creationTime = machine.creationTime if machine.creationTime else None
        acl = list()
        machine_acl = authenticator.auth().getVMachineAcl(machine.id)
        machinedict = machine.dump()
        for _, ace in machine_acl.iteritems():
            acl.append(
                {
                    "userGroupId": ace["userGroupId"],
                    "type": ace["type"],
                    "canBeDeleted": ace["canBeDeleted"],
                    "right": "".join(sorted(ace["right"])),
                    "status": ace["status"],
                }
            )
        return {
            "id": machine.id,
            "cloudspaceid": machine.cloudspaceId,
            "acl": acl,
            "disks": disks,
            "name": machine.name,
            "description": machine.descr,
            "hostname": machine.hostName,
            "status": machine.status,
            "imageid": machine.imageId,
            "osImage": osImage,
            "sizeid": machine.sizeId,
            "memory": machine.memory,
            "vcpus": machine.vcpus,
            "interfaces": machinedict["nics"],
            "storage": storage,
            "accounts": machinedict["accounts"],
            "locked": locked,
            "updateTime": updateTime,
            "creationTime": creationTime,
        }

    # Authentication (permissions) are checked while retrieving the machines
    def list(self, cloudspaceId, **kwargs):
        """
        List the deployed machines in a space. Filtering based on status is possible
        :param cloudspaceId: id of cloud space in which machine exists @tags: optional
        :return list of dict with each element containing the machine details

        """
        ctx = kwargs["ctx"]
        if not cloudspaceId:
            raise exceptions.BadRequest("Please specify a cloudsapce ID.")
        cloudspaceId = int(cloudspaceId)
        fields = [
            "id",
            "referenceId",
            "cloudspaceid",
            "hostname",
            "imageId",
            "name",
            "nics",
            "sizeId",
            "status",
            "stackId",
            "disks",
            "creationTime",
            "updateTime",
            "memory",
            "vcpus",
        ]

        user = ctx.env["beaker.session"]["user"]
        userobj = j.core.portal.active.auth.getUserInfo(user)
        groups = userobj.groups
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        auth = authenticator.auth()
        acl = auth.expandAclFromCloudspace(user, groups, cloudspace, explicit=True)
        q = {
            "cloudspaceId": cloudspaceId,
            "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
            "type": "VIRTUAL",
        }
        if "R" not in acl and "A" not in acl:
            q["acl.userGroupId"] = user

        query = {"$query": q, "$fields": fields}
        results = self.models.vmachine.search(query)[1:]
        machines = []
        alldisks = list(itertools.chain(*[m["disks"] for m in results]))
        query = {"$query": {"id": {"$in": alldisks}}, "$fields": ["id", "sizeMax"]}
        disks = {
            disk["id"]: disk.get("sizeMax", 0)
            for disk in self.models.disk.search(query, size=0)[1:]
        }
        for res in results:
            size = sum(disks.get(diskid, 0) for diskid in res["disks"])
            res["storage"] = size
            machines.append(res)
        return machines

    def _getMachine(self, machineId):
        machineId = int(machineId)
        return self.models.vmachine.get(machineId)

    @authenticator.auth(acl={"cloudspace": set("X")})
    def restore(self, machineId, reason, **kwargs):
        """
        Restore a deleted machine

        :param machineId: id of the machine
        """
        machine = self.models.vmachine.searchOne({"id": int(machineId)})
        if not machine:
            raise exceptions.NotFound("Machine ID %s was not found" % machineId)
        cloudspace = self.models.cloudspace.get(machine["cloudspaceId"])
        if machine["status"] != resourcestatus.Machine.DELETED:
            raise exceptions.BadRequest("Can't restore a non deleted machine")
        if (
            cloudspace.status in resourcestatus.Cloudspace.INVALID_STATES
            and "csrestore" not in kwargs
        ):
            raise exceptions.BadRequest(
                "Cannot restore a machine on a deleted cloudspace"
            )
        with self.models.account.lock(cloudspace.accountId):
            vcpus = machine["vcpus"]
            memory = machine["memory"]
            diskids = machine["disks"]
            totaldisksize = 0
            for diskid in diskids:
                disk = self.models.disk.get(diskid)
                totaldisksize += disk.sizeMax
            j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
                machine["cloudspaceId"], vcpus, memory / 1024.0, totaldisksize
            )

            nic = machine["nics"][0]
            nic["type"] = "bridge"
            nic["ipAddress"] = self.cb.cloudspace.network.getFreeIPAddress(cloudspace)
            machine["status"] = resourcestatus.Machine.HALTED
            machine["updateTime"] = int(time.time())
            machine["deletionTime"] = 0
            self.models.vmachine.set(machine)
        gevent.spawn(
            self.cb.cloudspace.update_firewall,
            cloudspace,
            ctx=j.core.portal.active.requestContext,
        )
        self.models.disk.updateSearch(
            {"id": {"$in": machine["disks"]}},
            {"$set": {"status": resourcestatus.Disk.CREATED}},
        )
        return True

    @authenticator.auth(acl={"machine": set("C")})
    def snapshot(self, machineId, name, force=False, **kwargs):
        """
        Take a snapshot of the machine

        :param machineId: id of the machine to snapshot
        :param name: name to give snapshot
        :param force: force create new snapshot if old snapshots with the same name already exists
        :return the dict of diskguids:snapshotguids
        """
        snapshots = self.listSnapshots(machineId)
        for snapshot in snapshots:
            if snapshot.get("name", "") == name:
                if force:
                    self.deleteSnapshot(machineId=machineId, name=name)
                else:
                    raise exceptions.BadRequest(
                        "Snapshot with the same name exists for this machine"
                    )
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        snapshots = provider.ex_create_snapshot(node, name)
        return snapshots

    @authenticator.auth(acl={"machine": set("R")})
    def listSnapshots(self, machineId, **kwargs):
        """
        List the snapshots of the machine

        :param machineId: id of the machine
        :return: list with the available snapshots
        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        if machine.status in resourcestatus.Machine.INVALID_STATES:
            raise exceptions.NotFound("Machine %s not found" % machineId)
        node.name = "vm-%s" % machineId
        snapshots = provider.ex_list_snapshots(node)
        snap_dict = {}
        for snapshot in snapshots:
            snapshot["name"] = j.tools.text.toStr(snapshot["name"])
            if snapshot["name"] and not snapshot["name"].endswith("_DELETING"):
                if snapshot["name"] not in snap_dict:
                    snap_dict[snapshot["name"]] = snapshot
        result = snap_dict.values()
        result.sort(key=lambda snapshot: snapshot["epoch"])
        return result

    @authenticator.auth(acl={"machine": set("X")})
    def deleteSnapshot(self, machineId, epoch=None, name=None, **kwargs):
        """
        Delete a snapshot of the machine

        :param machineId: id of the machine
        :param epoch: epoch time of snapshot
        """
        if not name and not epoch:
            raise exceptions.BadRequest(
                "Epoch or name should be passed to delete the snapshot"
            )
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        provider.ex_delete_snapshot(node, epoch, name)["state"]
        return True

    @authenticator.auth(acl={"machine": set("X")})
    @RequireState(
        resourcestatus.Machine.HALTED,
        "A snapshot can only be rolled back to a stopped Machine",
    )
    def rollbackSnapshot(self, machineId, epoch=None, name=None, **kwargs):
        """
        Rollback a snapshot of the machine

        :param machineId: id of the machine
        :param epoch: epoch time of snapshot (may get unexpected results)
        :param name: name of the snap shot to be rolled back (recommended)
        """
        if not epoch and not name:
            raise exceptions.BadRequest("Epoch or name should be passed to rollback")

        for snapshot in self.listSnapshots(machineId):
            if self._match_snapshot(snapshot, name, epoch):
                break
        else:
            raise exceptions.BadRequest(
                "No snapshots found with params: name %s , epoch %s" % (name, epoch)
            )

        provider, node, _ = self.cb.getProviderAndNode(machineId)
        return provider.ex_rollback_snapshot(node, epoch, name)

    def _match_snapshot(self, snapshot, name=None, epoch=None):
        if name:
            if name != snapshot["name"]:
                return False
        if epoch:
            if epoch != snapshot["epoch"]:
                return False
        return True

    @authenticator.auth(acl={"machine": set("C")})
    def update(self, machineId, name=None, description=None, **kwargs):
        """
        Change basic properties of a machine
        Name, description can be changed with this action.

        :param machineId: id of the machine
        :param name: name of the machine
        :param description: description of the machine
        """
        machine = self._getMachine(machineId)
        if name:
            self.cb.machine.assertName(machine.cloudspaceId, name)
            machine.name = name
        if description:
            machine.descr = description
        return self.models.vmachine.set(machine)[0]

    @authenticator.auth(acl={"machine": set("R")})
    def getConsoleUrl(self, machineId, **kwargs):
        """
        Get url to connect to console

        :param machineId: id of the machine to connect to console
        :return one time url used to connect ot console

        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        if machine.status in resourcestatus.Machine.INVALID_STATES:
            raise exceptions.NotFound("Machine %s not found" % machineId)
        if machine.status != resourcestatus.Machine.RUNNING:
            return None
        return provider.ex_get_console_url(node)

    @authenticator.auth(acl={"cloudspace": set("C")})
    @RequireState(
        resourcestatus.Machine.HALTED,
        "A clone can only be taken from a stopped Virtual Machine",
    )
    def clone(
        self,
        machineId,
        name,
        cloudspaceId=None,
        snapshottimestamp=None,
        snapshotname=None,
        **kwargs
    ):
        """
        Clone the machine

        :param machineId: id of the machine to clone
        :param name: name of the cloned machine
        :return id of the new cloned machine
        """
        machine = self._getMachine(machineId)

        if self.models.disk.count({"id": {"$in": machine.disks}, "type": "P"}) > 0:
            raise exceptions.BadRequest("Can't clone a vm with physical disks attached")

        if cloudspaceId is None:
            cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
        else:
            arg_cloudspace = self.models.cloudspace.get(cloudspaceId)
            if not arg_cloudspace:
                raise exceptions.NotFound("Cloudspace %s not found" % cloudspaceId)
            vm_cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
            if arg_cloudspace.accountId != vm_cloudspace.accountId:
                raise exceptions.MethodNotAllowed(
                    "Cannot clone a machine from a different account."
                )
            cloudspace = arg_cloudspace

        if machine.cloneReference:
            raise exceptions.MethodNotAllowed("Cannot clone a cloned machine.")

        # validate capacity of the vm
        query = {"$fields": ["id", "sizeMax"], "$query": {"id": {"$in": machine.disks}}}
        totaldisksize = sum(
            [disk["sizeMax"] for disk in self.models.disk.search(query)[1:]]
        )
        j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
            cloudspace.id, machine.vcpus, machine.memory / 1024.0, totaldisksize
        )

        # clone vm model
        self.cb.machine.assertName(machine.cloudspaceId, name)
        clone = self.models.vmachine.new()
        clone.cloudspaceId = cloudspace.id
        clone.name = name
        clone.descr = machine.descr
        clone.imageId = machine.imageId
        if machine.sizeId:
            clone.sizeId = machine.sizeId
        clone.memory = machine.memory
        clone.vcpus = machine.vcpus
        image = self.models.image.get(machine.imageId)
        clone.cloneReference = machine.id
        clone.acl = machine.acl
        clone.creationTime = int(time.time())
        clone.type = "VIRTUAL"
        password = "Unknown"
        for account in machine.accounts:
            newaccount = clone.new_account()
            newaccount.login = account.login
            newaccount.password = account.password
            password = account.password
        clone.id = self.models.vmachine.set(clone)[0]

        diskmapping = []

        _, node, machine = self.cb.getProviderAndNode(machineId)
        stack = self.cb.getBestStack(
            cloudspace.gid, machine.imageId, memory=machine.memory
        )
        provider = self.cb.getProviderByStackId(stack["id"])

        totaldisksize = 0
        for diskId in machine.disks:
            origdisk = self.models.disk.get(diskId)
            if origdisk.type == "M":
                continue
            clonedisk = self.models.disk.new()
            clonedisk.name = origdisk.name
            clonedisk.gid = origdisk.gid
            clonedisk.order = origdisk.order
            clonedisk.accountId = origdisk.accountId
            clonedisk.type = origdisk.type
            clonedisk.descr = origdisk.descr
            clonedisk.sizeMax = origdisk.sizeMax
            clonedisk.status = resourcestatus.Disk.MODELED
            clonediskId = self.models.disk.set(clonedisk)[0]
            clone.disks.append(clonediskId)
            volume = j.apps.cloudapi.disks.getStorageVolume(origdisk, provider, node)
            if clonedisk.type == "B":
                disk_name = "vm-{0}/bootdisk-vm-{0}".format(clone.id)
            else:
                disk_name = "volumes/volume_{}".format(clonediskId)
            diskmapping.append((volume, disk_name))
            totaldisksize += clonedisk.sizeMax

        clone.id = self.models.vmachine.set(clone)[0]
        if not snapshotname and not snapshottimestamp:
            disks_snapshots = self.snapshot(machineId, name)
        else:
            disks_snapshots = {}
            snapshots = self.listSnapshots(machineId)
            for snapshot in snapshots:
                if snapshotname and snapshot["name"] == snapshotname:
                    disks_snapshots[snapshot["diskguid"]] = snapshot["guid"]
                elif snapshottimestamp and snapshot["timestamp"] == snapshottimestamp:
                    disks_snapshots[snapshot["diskguid"]] = snapshot["guid"]

        try:
            userdata, metadata = self.cb.machine.get_user_meta_data(clone.name, password, image.type)
            node = provider.ex_clone(
                userdata,
                metadata,
                image.type,
                {"memory": machine.memory, "vcpus": machine.vcpus},
                clone.id,
                cloudspace.networkId,
                diskmapping,
                disks_snapshots,
            )
            if node == -1:
                raise exceptions.ServiceUnavailable(
                    "Not enough resources available to host clone"
                )
            self.cb.machine.updateMachineFromNode(clone, node, provider.stack)
        except:
            self.cb.machine.cleanup(clone)
            raise
        self.models.disk.updateSearch(
            {"id": {"$in": clone.disks}},
            {"$set": {"status": resourcestatus.Disk.ASSIGNED}},
        )
        gevent.spawn(
            self.cb.cloudspace.update_firewall,
            cloudspace,
            ctx=j.core.portal.active.requestContext,
        )
        return clone.id

    @authenticator.auth(acl={"machine": set("R")})
    def getHistory(self, machineId, size, **kwargs):
        """
        Get machine history

        :param machineId: id of the machine
        :param size: number of entries to return
        :return: list of the history of the machine
        """
        provider, node, machine = self.cb.getProviderAndNode(machineId)
        if machine.status in resourcestatus.Machine.INVALID_STATES:
            raise exceptions.NotFound("Machine %s not found" % machineId)
        tags = "machineId:{}(\D|$)".format(machineId)
        results = []
        for audit in self.sysmodels.audit.search({"tags": {"$regex": tags}})[1:]:
            parts = audit["call"].split("/")
            call = "/".join(parts[-2:])
            if parts[-1] in [
                "get",
                "getHistory",
                "listSnapshots",
                "list",
                "getConsoleUrl",
            ]:
                continue
            results.append(
                {
                    "epoch": audit["timestamp"],
                    "message": "User {} called {}".format(audit["user"], call),
                }
            )
        return results

    @authenticator.auth(acl={"cloudspace": set("X"), "machine": set("U")})
    def addUser(self, machineId, userId, accesstype, **kwargs):
        """
        Give a registered user access rights

        :param machineId: id of the machine
        :param userId: username or emailaddress of the user to grant access
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user was added successfully
        """
        user = self.cb.checkUser(userId, activeonly=False)
        if not user:
            raise exceptions.NotFound("User is not registered on the system")
        else:
            # Replace email address with ID
            userId = user["id"]

        self._addACE(machineId, userId, accesstype, userstatus="CONFIRMED")

        machineId = int(machineId)
        vmachine = self.models.vmachine.get(machineId)
        cloudspaceacl = authenticator.auth().getCloudspaceAcl(vmachine.cloudspaceId)
        if userId not in cloudspaceacl:
            j.apps.cloudapi.cloudspaces.addUser(
                cloudspaceId=vmachine.cloudspaceId,
                userId=userId,
                accesstype="R",
                explicit=False,
            )
        try:
            j.apps.cloudapi.users.sendShareResourceEmail(
                user, "machine", machineId, accesstype
            )
            return True
        except:
            self.deleteUser(machineId, userId, recursivedelete=False)
            raise

    def _addACE(self, machineId, userId, accesstype, userstatus="CONFIRMED"):
        """
        Add a new ACE to the ACL of the vmachine

        :param:machineId id of the vmachine
        :param userId: userid for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'W' for Write access
        :param userstatus: status of the user (CONFIRMED or INVITED)
        :return True if ACE was successfully added
        """
        self.cb.isValidRole(accesstype)
        machineId = int(machineId)
        vmachine = self.models.vmachine.get(machineId)
        vmachineacl = authenticator.auth().getVMachineAcl(machineId)
        if userId in vmachineacl:
            raise exceptions.BadRequest(
                "User already has access rights to this machine"
            )

        ace = vmachine.new_acl()
        ace.userGroupId = userId
        ace.type = "U"
        ace.right = accesstype
        ace.status = userstatus
        self.models.vmachine.updateSearch(
            {"id": machineId}, {"$push": {"acl": ace.obj2dict()}}
        )
        return True

    def _updateACE(self, machineId, userId, accesstype, userstatus):
        """
        Update an existing ACE in the ACL of a machine

        :param machineId: id of the cloudspace
        :param userId: userid for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'W' for Write access
        :param userstatus: status of the user (CONFIRMED or INVITED)
        :return True if ACE was successfully updated, False if no update is needed
        """
        self.cb.isValidRole(accesstype)
        machineId = int(machineId)
        vmachine = self.models.vmachine.get(machineId)
        vmachine_acl = authenticator.auth().getVMachineAcl(machineId)
        if userId in vmachine_acl:
            useracl = vmachine_acl[userId]
        else:
            raise exceptions.NotFound("User does not have any access rights to update")

        # If user has higher access rights on cloudspace then do not update, raise error
        if (
            "account_right" in useracl
            and set(accesstype) != set(useracl["account_right"])
            and set(accesstype).issubset(set(useracl["account_right"]))
        ):
            raise exceptions.Conflict(
                "User already has a higher access level to owning account"
            )
        # If user has higher access rights on cloudspace then do not update, raise error
        elif (
            "cloudspace_right" in useracl
            and set(accesstype) != set(useracl["cloudspace_right"])
            and set(accesstype).issubset(set(useracl["cloudspace_right"]))
        ):
            raise exceptions.Conflict(
                "User already has a higher access level to cloudspace"
            )
        # If user has the same access level on account or cloudspace then do not update,
        # fail silently
        if (
            "account_right" in useracl
            and set(accesstype) == set(useracl["account_right"])
        ) or (
            "cloudspace_right" in useracl
            and set(accesstype) == set(useracl["cloudspace_right"])
        ):
            # Remove machine level access rights if present, cleanup for backwards comparability
            self.models.vmachine.updateSearch(
                {"id": machineId}, {"$pull": {"userGroupId": userId, "type": "U"}}
            )
            return False
        else:
            # grant higher access level
            ace = vmachine.new_acl()
            ace.userGroupId = userId
            ace.type = "U"
            ace.right = accesstype
            ace.status = userstatus
            self.models.vmachine.updateSearch(
                {"id": machineId},
                {"$pull": {"acl": {"type": "U", "userGroupId": userId}}},
            )
            self.models.vmachine.updateSearch(
                {"id": machineId}, {"$push": {"acl": ace.obj2dict()}}
            )
        return True

    @authenticator.auth(acl={"cloudspace": set("X"), "machine": set("U")})
    def deleteUser(self, machineId, userId, **kwargs):
        """
        Revoke user access from the vmachine

        :param machineId: id of the machine
        :param userId: id or emailaddress of the user to remove
        :return True if user access was revoked from machine
        """

        result = self.models.vmachine.updateSearch(
            {"id": machineId}, {"$pull": {"acl": {"type": "U", "userGroupId": userId}}}
        )
        # Remove user Read access from account it no other machines or cloudspaces have this user and not explicitly added to account
        machineId = int(machineId)
        vmachine = self.models.vmachine.get(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        cloudspaceacl = authenticator.auth().getCloudspaceAcl(vmachine.cloudspaceId)
        if userId in cloudspaceacl:
            if not cloudspaceacl[userId].get("explicit", True):
                matched_vms = self.models.cloudspace.search(
                    {
                        "cloudspaceId": cloudspace.id,
                        "acl.userGroupId": userId,
                        "id": {"$ne": machineId},
                        "$fields": {"id"},
                    }
                )
                if matched_vms[0] == 0:
                    j.apps.cloudapi.cloudspaces.deleteUser(
                        cloudspaceId=cloudspace.id, userId=userId, recursivedelete=True
                    )
        if result["nModified"] == 0:
            # User was not found in access rights
            raise exceptions.NotFound(
                'User "%s" does not have access on the machine' % userId
            )
        return True

    @authenticator.auth(acl={"cloudspace": set("X"), "machine": set("U")})
    def updateUser(self, machineId, userId, accesstype, **kwargs):
        """
        Update user access rights. Returns True only if an actual update has happened.

        :param machineId: id of the machineId
        :param userId: userid/email for registered users or emailaddress for unregistered users
        :param accesstype: 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        :return True if user access was updated successfully
        """
        # Check if user exists in the system or is an unregistered invited user
        existinguser = self.sysmodels.user.search({"id": userId})[1:]
        if existinguser:
            userstatus = "CONFIRMED"
        else:
            userstatus = "INVITED"
        return self._updateACE(machineId, userId, accesstype, userstatus)

    @authenticator.auth(acl={"cloudspace": set("X")})
    def attachExternalNetwork(self, machineId, externalNetworkId=None, **kwargs):
        """
         Attach a external network to the machine

        :param machineId: id of the machine
        :param externalNetworkId: optional external network id to take ip address from
        :return: True if a external network was attached to the machine
        """
        provider, node, vmachine = self.cb.getProviderAndNode(machineId)
        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        for nic in vmachine.nics:
            if nic.type == "PUBLIC":
                tags = j.core.tags.getObject(nic.params)
                nicExternalNetId = int(tags.tags.get("externalnetworkId"))
                if externalNetworkId == nicExternalNetId:
                    return True

        # Check that attaching a external network will not exceed the allowed CU limits
        j.apps.cloudapi.cloudspaces.checkAvailablePublicIPs(cloudspace, 1)
        networkid = cloudspace.networkId
        netinfo = self.network.getExternalIpAddress(
            cloudspace.gid, cloudspace.accountId, externalNetworkId
        )
        if netinfo is None:
            raise RuntimeError("No available externalnetwork IPAddresses")
        pool, externalnetworkip = netinfo
        externalNetworkId = pool.id
        if not externalnetworkip:
            raise RuntimeError(
                "Failed to get externalnetworkip for networkid %s" % networkid
            )
        nic = vmachine.new_nic()
        nic.ipAddress = str(externalnetworkip)
        nic.params = j.core.tags.getTagString(
            [], {"gateway": pool.gateway, "externalnetworkId": str(pool.id)}
        )
        nic.type = "PUBLIC"
        try:
            iface = provider.attach_public_network(
                node, pool.vlan, nic.ipAddress, externalNetworkId
            )
        except:
            vmachine.nics = self._detachExternalNetworkFromModel(
                vmachine.nics, externalNetworkId
            )
            self.models.vmachine.set(vmachine)
            raise
        self.models.vmachine.set(vmachine)
        nic.deviceName = iface.target
        nic.macAddress = iface.mac
        self.models.vmachine.set(vmachine)
        return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def resize(self, machineId, sizeId=None, vcpus=None, memory=None, **kwargs):
        if sizeId and (vcpus or memory):
            raise exceptions.BadRequest(
                "sizeId and (vcpus or memory) are mutually exclusive"
            )
        # make sure that if u pass memory or vcpus u have to pass the other as well
        if (memory or vcpus) and not (memory and vcpus):
            raise exceptions.BadRequest(
                "cannot pass vcpus or memory without the other."
            )
        if sizeId == -1:
            sizeId = None
        if sizeId:
            size = self.models.size.get(sizeId)
            memory = size.memory
            vcpus = size.vcpus
        new_memory = memory
        new_vcpus = vcpus

        if new_memory % 2:
            raise exceptions.BadRequest("memory value should be an even number")

        provider, node, vmachine = self.cb.getProviderAndNode(machineId)
        # Validate that enough resources are available in the CU limits if size will be increased
        old_memory = vmachine.memory
        old_vcpus = vmachine.vcpus
        # Calcultate the delta in memory and vpcu only if new size is bigger than old size
        deltacpu = max(new_vcpus - old_vcpus, 0)
        deltamemorymb = new_memory - old_memory
        if deltamemorymb < 0 and vmachine.status != resourcestatus.Machine.HALTED:
            raise exceptions.BadRequest("Can not decrease memory on a running machine")
        if new_vcpus < old_vcpus and vmachine.status != resourcestatus.Machine.HALTED:
            raise exceptions.BadRequest("Can not decrease vcpus on a running machine")

        cloudspace = self.models.cloudspace.get(vmachine.cloudspaceId)
        with self.models.account.lock(cloudspace.accountId):
            deltamemory = max(deltamemorymb / 1024., 0)
            j.apps.cloudapi.cloudspaces.checkAvailableMachineResources(
                vmachine.cloudspaceId, numcpus=deltacpu, memorysize=deltamemory
            )

            newcpucount = None
            if new_vcpus > old_vcpus:
                newcpucount = new_vcpus
            success = True
            image = self.models.image.get(vmachine.imageId)
            if vmachine.status != resourcestatus.Machine.HALTED and image.hotResize:
                success = provider.ex_resize(
                    node=node, extramem=deltamemorymb, vcpus=newcpucount
                )

            new_values = {"memory": new_memory, "vcpus": new_vcpus, "sizeId": 0}
            if sizeId:
                new_values["sizeId"] = sizeId
            self.models.vmachine.updateSearch({"id": machineId}, {"$set": new_values})
            if not success:
                raise exceptions.Accepted(False)
            return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def detachExternalNetwork(self, machineId, externalNetworkId=None, **kwargs):
        """
        Detach the external network from the machine

        :param machineId: id of the machine
        :param externalNetworkId: optional external network id. If omitted all external networks will be detached
        :return: True if external network was detached from the machine
        """
        provider, node, vmachine = self.cb.getProviderAndNode(machineId)
        machine_nics = []
        for nic in vmachine.nics:
            nicdict = nic.obj2dict()
            if "type" not in nicdict or nicdict["type"] != "PUBLIC":
                machine_nics.append(nic)
                continue

            tags = j.core.tags.getObject(nic.params)
            externalNetId = int(tags.tags.get("externalnetworkId"))
            if externalNetworkId and externalNetworkId != externalNetId:
                machine_nics.append(nic)
                continue

            provider.detach_public_network(node, nic.macAddress)
            self.network.releaseExternalIpAddress(externalNetId, nic.ipAddress)
        vmachine.nics = machine_nics
        self.models.vmachine.set(vmachine)
        return True

    @authenticator.auth(acl={"cloudspace": set("X")})
    def listExternalNetworks(self, machineId, **kwargs):
        """
        List the external networks that the machine is attached to

        :param machineId: id of the machine
        :return: True if external network was detached from the machine
        """
        _, _, vmachine = self.cb.getProviderAndNode(machineId)

        result = list()
        for nic in vmachine.nics:
            if nic.type == "PUBLIC":
                tags = j.core.tags.getObject(nic.params)
                externalNetId = int(tags.tags.get("externalnetworkId"))
                result.append(int(externalNetId))
        return result

    def _detachExternalNetworkFromModel(self, nics, externalNetworkId=0):
        machine_nics = []
        for nic in nics:
            nicdict = nic.obj2dict()
            if "type" not in nicdict or nicdict["type"] != "PUBLIC":
                machine_nics.append(nic)
                continue
            tags = j.core.tags.getObject(nic.params)
            externalNetId = int(tags.tags.get("externalnetworkId"))
            if externalNetworkId and externalNetworkId != externalNetId:
                machine_nics.append(nic)
                continue
            self.network.releaseExternalIpAddress(externalNetId, nic.ipAddress)
        return machine_nics
