from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import resourcestatus
from cloudbrokerlib.authenticator import auth
from cloudbrokerlib.baseactor import BaseActor
import requests
import urllib
import math


class cloudbroker_image(BaseActor):
    def _checkimage(self, imageId):
        if not self.models.image.exists(imageId):
            raise exceptions.BadRequest('Image with id "%s" not found' % imageId)
        return self.models.image.get(imageId)

    @auth(groups=["level1", "level2", "level3"])
    def delete(self, imageId, reason, permanently=False, name=None, **kwargs):
        """
        Delete an image
        param:imageId id of image
        result bool
        """
        if name:
            image = self.models.image.searchOne({"id": imageId, "name": name})
            if not image:
                raise exceptions.BadRequest("Incorrect image name specified")
        return j.apps.cloudapi.images.deleteImage(imageId, permanently)

    @auth(groups=["level3"])
    def deleteImages(self, imageIds, reason, permanently=False, **kwargs):
        for imageId in imageIds:
            self.delete(imageId, reason, permanently)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def restore(self, imageId, reason, **kwargs):
        return j.apps.cloudapi.images.restore(imageId)

    @auth(groups=["level1", "level2", "level3"])
    def enable(self, imageId, **kwargs):
        """
        Enable an image
        param:imageId id of image
        result bool
        """
        image = self._checkimage(imageId)
        if image.status in resourcestatus.Image.INVALID_STATES:
            raise exceptions.BadRequest("Can not enable a deleted image")
        
        if image.status == resourcestatus.Image.CREATING:
            raise exceptions.BadRequest("Can not do  this action on uncreated Image")

        self.models.image.updateSearch(
            {"id": imageId}, {"$set": {"status": resourcestatus.Image.CREATED}}
        )

    @auth(groups=["level1", "level2", "level3"])
    def disable(self, imageId, **kwargs):
        """
        Disable an image
        param:imageId id of image
        result bool
        """
        image = self._checkimage(imageId)
        if image.status in resourcestatus.Image.INVALID_STATES:
            raise exceptions.BadRequest("Can not disable a deleted image")
        if image.status == resourcestatus.Image.CREATING:
            raise exceptions.BadRequest("Can not do  this action on uncreated Image")
        self.models.image.updateSearch(
            {"id": imageId}, {"$set": {"status": resourcestatus.Image.DISABLED}}
        )

    @auth(groups=["level1", "level2", "level3"])
    def updateNodes(self, imageId, enabledStacks, **kwargs):
        enabledStacks = enabledStacks or list()
        image = self._checkimage(imageId)
        enabledStacks = [int(x) for x in enabledStacks]
        self.models.stack.updateSearch(
            {"id": {"$in": enabledStacks}}, {"$addToSet": {"images": image.id}}
        )
        self.models.stack.updateSearch(
            {"id": {"$nin": enabledStacks}}, {"$pull": {"images": image.id}}
        )
        return True

    def _getImageSize(self, url):
        try:
            resp = requests.head(url)
            if resp.status_code != 200:
                raise exceptions.BadRequest(
                    "Failed to get url size, {}: {}".format(
                        resp.status_code, resp.content
                    )
                )
            if "Content-Length" not in resp.headers:
                raise exceptions.BadRequest("Failed to get url size")
            bytesize = resp.headers["Content-Length"]
        except requests.ConnectionError:
            raise exceptions.BadRequest("Failed to connect to url")
        except requests.exceptions.InvalidSchema:
            try:
                con = urllib.urlopen(url)
                bytesize = con.headers.getheader("content-length")
            except:
                raise exceptions.BadRequest("Failed to get url size")
        except requests.exceptions.MissingSchema:
            raise exceptions.BadRequest("Invalid url passed")
        try:
            bytesize = int(bytesize)
        except:
            raise exceptions.BadRequest("Failed to get url size")
        return bytesize

    @auth(groups=["level1", "level2", "level3"])
    def createImage(
        self,
        name,
        url,
        gid,
        imagetype,
        boottype,
        username=None,
        password=None,
        accountId=None,
        hotresize=True,
        **kwargs
    ):
        if accountId:
            account = self.models.account.searchOne({"id": accountId})
            if not account:
                raise exceptions.BadRequest("Specified accountId does not exist")
            elif account["status"] in resourcestatus.Account.INVALID_STATES:
                raise exceptions.BadRequest("Can not create an image on deleted Account")
        if boottype not in ["bios", "uefi"]:
            raise exceptions.BadRequest(
                "Invalid boottype, should be either uefi or bios"
            )
        bytesize = self._getImageSize(url)
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._createImage,
            (
                name,
                url,
                gid,
                imagetype,
                boottype,
                bytesize,
                username,
                password,
                accountId,
                hotresize,
                kwargs,
            ),
            {},
            "Creating Image {}".format(name),
            "Finished Creating Image",
            "Failed to create Image",
        )
        return True

    @auth(groups=["level1", "level2", "level3"])
    def syncCreateImage(
        self,
        name,
        url,
        gid,
        imagetype,
        boottype,
        username=None,
        password=None,
        accountId=None,
        hotresize=True,
        **kwargs
    ):
        if accountId and not self.models.account.exists(accountId):
            raise exceptions.BadRequest("Specified accountId does not exist")
        if boottype not in ["bios", "uefi"]:
            raise exceptions.BadRequest(
                "Invalid boottype, should be either uefi or bios"
            )
        bytesize = self._getImageSize(url)
        return self._createImage(
            name,
            url,
            gid,
            imagetype,
            boottype,
            bytesize,
            username,
            password,
            accountId,
            hotresize,
            kwargs,
        )

    @auth(groups=["level1", "level2", "level3"])
    def edit(
        self,
        imageId,
        name=None,
        username=None,
        password=None,
        accountId=None,
        hotResize=None,
        **kwargs
    ):
        if accountId and not self.models.account.exists(accountId):
            raise exceptions.BadRequest("Specified accountId does not exists")
        self._checkimage(imageId)
        update = {}
        if name:
            update["name"] = name
        if username:
            update["username"] = username
        if password:
            update["password"] = password
        if accountId is not None:
            update["accountId"] = accountId

        if hotResize == "False":
            update["hotResize"] = False
        elif hotResize == "True":
            update["hotResize"] = True
        if update:
            self.models.image.updateSearch({"id": imageId}, {"$set": update})

    def _createImage(
        self,
        name,
        url,
        gid,
        imagetype,
        boottype,
        bytesize,
        username,
        password,
        accountId,
        hotresize,
        kwargs,
    ):
        ctx = kwargs["ctx"]
        gbsize = int(math.ceil(j.tools.units.bytes.toSize(bytesize, "", "G")))
        provider = self.cb.getProviderByGID(gid)
        image = self.models.image.new()
        image.name = name
        image.gid = gid
        image.url = url
        image.type = imagetype
        image.username = username
        image.password = password
        image.accountId = accountId or 0
        image.status = resourcestatus.Image.CREATING
        image.size = gbsize
        image.bootType = boottype
        image.hotResize = hotresize
        image.lastModified = j.system.net.getServerFileLastModified(url)
        volume = None
        try:
            image.id = self.models.image.set(image)[0]
            volume = provider.create_volume(
                gbsize, "templates/image_{}".format(image.id), vpool="vmstor", type='C'
            )
            self.models.image.updateSearch(
                {"id": image.id}, {"$set": {"referenceId": volume.vdiskguid}}
            )
            image.referenceId = volume.vdiskguid
            size = provider._execute_agent_job(
                "cloudbroker_import_image",
                role="storagedriver",
                url=url,
                timeout=3600,
                volumeid=volume.id,
                eventstreamid=ctx.events.eventstreamid,
                disksize=gbsize,
                ovs_connection=provider.ovs_connection,
                istemplate=True,
            )
        except BaseException as e:
            j.errorconditionhandler.processPythonExceptionObject(e)
            if volume:
                provider.destroy_volume(volume)
            if self.models.image.exists(image.id):
                self.models.image.delete(image.id)
            raise
        self.models.image.updateSearch(
            {"id": image.id},
            {"$set": {"status": resourcestatus.Image.CREATED, "size": size}},
        )
        self.models.stack.updateSearch(
            {"gid": gid}, {"$addToSet": {"images": image.id}}
        )
        return True

    @auth(groups=["level1", "level2", "level3"])
    def deleteCDROMImage(
        self, diskId, permanently=False, name=None, reason=None, **kwargs
    ):
        return j.apps.cloudapi.disks.delete(
            diskId, True, permanently, name, reason, **kwargs
        )

    @auth(groups=["level1", "level2", "level3"])
    def createCDROMImage(self, name, url, gid, accountId=None, **kwargs):
        if accountId:
            account = self.models.account.searchOne({"id": accountId})
            if not account:
                raise exceptions.BadRequest("Specified accountId does not exist")
            elif account["status"] in resourcestatus.Account.INVALID_STATES:
                raise exceptions.BadRequest("Can not create a CD-ROM image on deleted Account")
        bytesize = self._getImageSize(url)
        ctx = kwargs["ctx"]
        ctx.events.runAsync(
            self._createCDROMImage,
            (name, url, gid, bytesize, accountId, kwargs),
            {},
            "Creating CD-ROM Image {}".format(name),
            "Finished Creating CD-ROM Image",
            "Failed to create CD-ROM Image",
        )
        return True

    def _createCDROMImage(self, name, url, gid, bytesize, accountId, kwargs):
        ctx = kwargs["ctx"]
        gbsize = int(math.ceil(j.tools.units.bytes.toSize(bytesize, "", "G")))
        provider = self.cb.getProviderByGID(gid)
        disk = self.models.disk.new()
        disk.name = name
        disk.gid = gid
        disk.accountId = accountId
        disk.status = resourcestatus.Disk.CREATING
        disk.type = "C"
        disk.sizeMax = gbsize
        disk.id = self.models.disk.set(disk)[0]
        volume = None
        try:
            volume = provider.create_volume(
                gbsize, "rescuedisk/disk_{}".format(disk.id), vpool="vmstor", type='C'
            )
            self.models.disk.updateSearch(
                {"id": disk.id}, {"$set": {"referenceId": volume.id}}
            )
            disk.referenceId = volume.id
            size = provider._execute_agent_job(
                "cloudbroker_import_image",
                role="storagedriver",
                url=url,
                timeout=3600,
                volumeid=volume.id,
                eventstreamid=ctx.events.eventstreamid,
                disksize=gbsize,
                ovs_connection=provider.ovs_connection,
            )
        except BaseException as e:
            j.errorconditionhandler.processPythonExceptionObject(e)
            if volume:
                provider.destroy_volume(volume)
            if self.models.disk.exists(disk.id):
                self.models.disk.delete(disk.id)
            raise
        self.models.disk.updateSearch(
            {"id": disk.id},
            {"$set": {"status": resourcestatus.Disk.CREATED, "sizeMax": size}},
        )
