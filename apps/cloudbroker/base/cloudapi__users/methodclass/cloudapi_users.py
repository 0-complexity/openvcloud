from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor
import re, string, random, time
import json


VALIDATION_TIME = 7 * 24 * 60 * 60


class cloudapi_users(BaseActor):
    """
    User management

    """
    def authenticate(self, username, password, **kwargs):
        """
        The function evaluates the provided username and password and returns a session key.
        The session key can be used for doing api requests. E.g this is the authkey parameter in every actor request.
        A session key is only vallid for a limited time.
        param:username username to validate
        param:password password to validate
        result str,,session
        """
        ctx = kwargs["ctx"]
        return j.apps.system.usermanager.authenticate(
            name=username, secret=password, ctx=ctx
        )

    def get(self, username, **kwargs):
        """
        Get information of a existing username based on username id
        param:username username of the user
        result:
        """
        ctx = kwargs["ctx"]
        logedinuser = ctx.env["beaker.session"]["user"]
        if logedinuser != username:
            ctx.start_response("403 Forbidden", [])
            return "Forbidden"

        user = j.core.portal.active.auth.getUserInfo(username)
        if user:
            try:
                data = json.loads(user.data)
            except:
                data = {}
            return {"username": user.id, "emailaddresses": user.emails, "data": data}
        else:
            ctx.start_response("404 Not Found", [])
            return "User not found"

    def setData(self, data, **kwargs):
        """
        Set user data
        param:username username of the user
        result:
        """
        ctx = kwargs["ctx"]
        username = ctx.env["beaker.session"]["user"]
        if username == "guest":
            ctx.start_response("403 Forbidden", [])
            return "Forbidden"

        if not isinstance(data, dict):
            try:
                data = json.loads(data)
            except:
                raise exceptions.BadRequest("data needs to be in json format")

        user = j.core.portal.active.auth.getUserInfo(username)
        if user:
            try:
                userdata = json.loads(user.data)
            except:
                userdata = {}
            userdata.update(data)
            user.data = json.dumps(userdata)
            self.sysmodels.user.set(user)
            return True
        else:
            ctx.start_response("404 Not Found", [])
            return "User not found"

    def getMatchingUsernames(self, usernameregex, limit=5, **kwargs):
        """
        Get a list of the matching usernames for a given string

        :param usernameregex: regex of the usernames to searched for
        :param limit: the number of usernames to return
        :return: list of dicts with the username and url of the gravatar of the user
        """
        if limit > 20:
            raise exceptions.BadRequest(
                "Cannot return more than 20 usernames while matching users"
            )

        matchingusers = self.sysmodels.user.search(
            {"id": {"$regex": usernameregex}}, size=limit
        )[1:]

        if matchingusers:

            def userinfo(user):
                emailhash = j.tools.hash.md5_string(next(iter(user["emails"]), ""))
                return {
                    "username": user["id"],
                    "gravatarurl": "http://www.gravatar.com/avatar/%s" % emailhash,
                }

            return map(userinfo, matchingusers)
        else:
            return []

    def sendInviteLink(
        self, emailaddress, resourcetype, resourceid, accesstype, **kwargs
    ):
        """
        Send an invitation for a link to share a vmachine, cloudspace, account management
        inviting a new user to register and access them

        :param emailaddress: emailaddress of the user that will be invited
        :param resourcetype: the type of the resource that will be shared (account,
                             cloudspace, vmachine)
        :param resourceid: the id of the resource that will be shared
        :param accesstype: 'R' for read only access, 'RCX' for Write access, 'ARCXDU' for admin
        :return True if email was was successfully sent
        """

        if not re.search("^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}$", emailaddress):
            raise exceptions.PreconditionFailed(
                "Specified email address is in an invalid format"
            )

        existinginvitationtoken = self.models.inviteusertoken.search(
            {"email": emailaddress}
        )[1:]

        if existinginvitationtoken:
            # Resend the same token in a new email for the newly shared resource
            invitationtoken = self.models.inviteusertoken.get(
                existinginvitationtoken[0]["id"]
            )
        else:
            # genrerate a new token
            generatedtoken = "".join(
                random.choice(string.ascii_lowercase + string.digits)
                for _ in xrange(64)
            )
            invitationtoken = self.models.inviteusertoken.new()
            invitationtoken.id = generatedtoken
            invitationtoken.email = emailaddress

        invitationtoken.lastInvitationTime = int(time.time())
        self.models.inviteusertoken.set(invitationtoken)
        templatename = "invite_external_users"
        extratemplateargs = {"invitationtoken": invitationtoken.id}
        return self._sendShareEmail(
            emailaddress,
            resourcetype,
            resourceid,
            accesstype,
            templatename,
            extratemplateargs,
        )

    def sendShareResourceEmail(self, user, resourcetype, resourceid, accesstype):
        """
        Send an email to a registered users to inform a vmachine, cloudspace, account management
        has been shared with them

        :param user: user object
        :param resourcetype: the type of the resource that will be shared (account,
                             cloudspace, vmachine)
        :param resourceid: the id of the resource that will be shared
        :param accesstype: 'R' for read only access, 'RCX' for Write access, 'ARCXDU' for admin
        :return True if email was successfully sent
        """
        sendAccessEmails = True
        if resourcetype.lower() == "account":
            account = self.models.account.get(resourceid)
            sendAccessEmails = account.sendAccessEmails
        elif resourcetype.lower() == "cloudspace":
            cloudspace = self.models.cloudspace.get(resourceid)
            account = self.models.account.get(cloudspace.accountId)
            sendAccessEmails = account.sendAccessEmails
        elif resourcetype.lower() == "machine":
            machine = self.models.vmachine.get(resourceid)
            cloudspace = self.models.cloudspace.get(machine.cloudspaceId)
            account = self.models.account.get(cloudspace.accountId)
            sendAccessEmails = account.sendAccessEmails

        if not sendAccessEmails:
            return False
        templatename = "invite_internal_users"
        extratemplateargs = {"username": user["id"], "activated": user["active"]}
        if user["emails"]:
            return self._sendShareEmail(
                user["emails"][0],
                resourcetype,
                resourceid,
                accesstype,
                templatename,
                extratemplateargs,
            )
        return True

    def _sendShareEmail(
        self,
        emailaddress,
        resourcetype,
        resourceid,
        accesstype,
        templatename,
        extratemplateargs=None,
    ):
        """

        :param emailaddress: emailaddress of the registered user
        :param resourcetype: the type of the resource that will be shared (account,
                             cloudspace, vmachine)
        :param resourceid: the id of the resource that will be shared
        :param accesstype: 'R' for read only access, 'RCX' for Write access, 'ARCXDU' for admin
        :param templatename: name of the template to be used for sending the email (templates are
            located under cloudbroker/email/users/)
        :param extratemplateargs: optional extra arguments to be passed to the template
        :return: True if email was was successfully sent
        """
        # Build up message subject, body and send it
        fromaddr = self.hrd.get("instance.openvcloud.supportemail")
        toaddrs = [emailaddress]

        if resourcetype.lower() == "account":
            accountobj = self.models.account.get(resourceid)
            resourcename = accountobj.name
        elif resourcetype.lower() == "cloudspace":
            cloudspaceobj = self.models.cloudspace.get(resourceid)
            resourcename = cloudspaceobj.name
        elif resourcetype.lower() == "machine":
            machineobj = self.models.vmachine.get(resourceid)
            resourcename = machineobj.name

        if set(accesstype) == set("ARCXDU"):
            accessrole = "Admin"
        elif set(accesstype) == set("RCX"):
            accessrole = "Write"
        elif set(accesstype) == set("R"):
            accessrole = "Read"
        else:
            raise exceptions.PreconditionFailed(
                "Unidentified access rights (%s) have been set." % accesstype
            )

        args = {
            "email": emailaddress,
            "resourcetype": resourcetype,
            "resourcename": resourcename,
            "resourceid": resourceid,
            "accessrole": accessrole,
            "portalurl": j.apps.cloudapi.locations.getUrl(),
            "emailaddress": emailaddress,
        }

        if extratemplateargs:
            args.update(extratemplateargs)

        subject = j.core.portal.active.templates.render(
            "cloudbroker/email/users/%s.subject.txt" % templatename, **args
        )
        body = j.core.portal.active.templates.render(
            "cloudbroker/email/users/%s.html" % templatename, **args
        )

        j.clients.email.send(toaddrs, fromaddr, subject, body)

        return True

    def isValidInviteUserToken(self, inviteusertoken, emailaddress, **kwargs):
        """
        Check if the inviteusertoken and emailaddress pair are valid and matching

        :param inviteusertoken: the token that was previously sent to the invited user email
        :param emailaddress: email address for the user
        :return: True if token and emailaddress are valid, otherwise False
        """
        if not self.models.inviteusertoken.exists(inviteusertoken):
            raise exceptions.BadRequest("Invalid invitation token.")

        inviteusertokenobj = self.models.inviteusertoken.get(inviteusertoken)
        if inviteusertokenobj.email != emailaddress:
            # Email address of user isn't the same as the address the user was invited with
            raise exceptions.BadRequest("Invalid invitation token.")

        return True
