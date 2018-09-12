from cloudbrokerlib import authenticator
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor
from cloudbrokerlib import resourcestatus
import time


class cloudapi_images(BaseActor):
    """
    Lists all the images. A image is a template which can be used to deploy machines.

    """

    def list(self, accountId, cloudspaceId, **kwargs):
        """
        List the available images, filtering can be based on the cloudspace and the user which is doing the request
        """
        fields = [
            "id",
            "name",
            "description",
            "type",
            "size",
            "username",
            "accountId",
            "status",
        ]
        if accountId:
            q = {
                "referenceId": {"$nin": ["", None]},
                "status": resourcestatus.Image.CREATED,
                "accountId": {"$in": [0, int(accountId)]},
            }
        else:
            q = {
                "referenceId": {"$nin": ["", None]},
                "status": resourcestatus.Image.CREATED,
                "accountId": 0,
            }
        query = {"$query": q, "$fields": fields}

        if cloudspaceId:
            cloudspace = self.models.cloudspace.get(cloudspaceId)
            q["gid"] = cloudspace.gid

        results = self.models.image.search(query)[1:]

        def imagesort(image_a, image_b):
            def getName(image):
                name = "%d %s %s" % (
                    image["accountId"] or 0,
                    image["type"],
                    image["name"],
                )
                return name

            return cmp(getName(image_a), getName(image_b))

        return sorted(results, cmp=imagesort)

    def deleteImage(self, imageId, permanently):
        image = self.models.image.get(imageId)
        if image.status == resourcestatus.Image.DESTROYED:
            return True
        references = self.models.vmachine.count(
            {"imageId": imageId, "status": {"$ne": resourcestatus.Machine.DESTROYED}}
        )
        if references and permanently:
            raise exceptions.Conflict("Can not delete an image which is still used")
        if image.status != resourcestatus.Image.DELETED:
            if image.status != resourcestatus.Image.CREATED:
                raise exceptions.Forbidden(
                    "Can not delete an image which is not created yet."
                )

        deleted_state = resourcestatus.Image.DELETED
        if permanently:
            deleted_state = resourcestatus.Image.DESTROYED
            provider = self.cb.getProviderByGID(image.gid)
            provider.ex_delete_template(image.referenceId)

        self.models.image.updateSearch(
            {"id": imageId},
            {"$set": {"status": deleted_state, "deletionTime": int(time.time())}},
        )
        self.models.stack.updateSearch(
            {"images": imageId}, {"$pull": {"images": imageId}}
        )
        return True

    def delete(self, imageId, permanently=False, **kwargs):
        """
        Delete an image

        :param imageId: id of the image to delete
        :return True if image was deleted successfully
        """
        ctx = kwargs["ctx"]
        user = ctx.env["beaker.session"]["user"]
        image = self.models.image.get(imageId)
        if image.accountId <= 0:
            raise exceptions.MethodNotAllowed("Can not delete system images")
        account = self.models.account.get(image.accountId)
        auth = authenticator.auth(acl={"account": set("C")})
        auth.isAuthorized(user, account)
        return self.deleteImage(imageId, permanently)

    def get_or_create_by_name(self, name, add_to_all_stacks=True):
        images = self.models.image.search({"name": name})
        if images[0]:
            image = self.models.image.new()
            image.load(images[1])
        else:
            image = self.models.image.new()
            image.name = name
            image.provider_name = "libvirt"
            image.size = 0
            image.status = resourcestatus.Image.CREATED
            image.type = "Linux"
            imageid = self.models.image.set(image)[0]
            image.id = imageid
        if add_to_all_stacks:
            self.models.stack.updateSearch(
                {"images": {"$ne": image.id}}, {"$addToSet": {"images": image.id}}
            )
        return image

    def restore(self, imageId, **kwargs):
        image = self.models.image.searchOne({"id": imageId})
        if not image:
            raise exceptions.BadRequest('Image with id "%s" not found' % imageId)
        account = self.models.account.searchOne({"id": image["accountId"]})
        if (
            account
            and account["status"] in resourcestatus.Account.INVALID_STATES
            and "imgrestore" not in kwargs
        ):
            raise exceptions.BadRequest("Cannot restore an image on a deleted account")
        if image["status"] != resourcestatus.Image.DELETED:
            raise exceptions.BadRequest("Can only restore a deleted image")
        self.models.image.updateSearch(
            {"id": image["id"]},
            {"$set": {"status": resourcestatus.Image.CREATED, "deletionTime": 0}},
        )
        self.models.stack.updateSearch(
            {"gid": image["gid"]}, {"$addToSet": {"images": image["id"]}}
        )
        return True
