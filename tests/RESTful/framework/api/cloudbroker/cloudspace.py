import random
from framework.api import utils


class Cloudspace:
    def __init__(self, api_client):
        self._api = api_client

    def addExtraIP(self, cloudspaceId, ipaddress):
        return self._api.cloudbroker.cloudspace.addExtraIP(
            cloudspaceId=cloudspaceId, ipaddress=ipaddress
        )

    def addUser(self, username, cloudspaceId, **kwargs):
        data = {
            "username": username,
            "cloudspaceId": cloudspaceId,
            "accesstype": random.choice(["R", "RCX", "ARCX"]),
        }
        data.update(**kwargs)
        return data, self._api.cloudbroker.cloudspace.addUser(**data)

    def create(self, accountId, location, access, **kwargs):
        data = {
            "accountId": accountId,
            "location": location,
            "access": access,
            "name": utils.random_string(),
            "maxMemoryCapacity": -1,
            "maxVDiskCapacity": -1,
            "maxCPUCapacity": -1,
            "maxNetworkPeerTransfer": -1,
            "maxNumPublicIP": -1,
            "allowedVMSizes": [],
            "privatenetwork": "",
        }
        data.update(**kwargs)
        return data, self._api.cloudbroker.cloudspace.create(**data)

    def update(self, cloudspaceId, **kwargs):
        data = {
            "cloudspaceId": cloudspaceId,
            "name": utils.random_string(),
            "maxMemoryCapacity": -1,
            "maxVDiskCapacity": -1,
            "maxCPUCapacity": -1,
            "maxNetworkPeerTransfer": -1,
            "maxNumPublicIP": -1,
            "allowedVMSizes": [],
        }
        data.update(**kwargs)
        return data, self._api.cloudbroker.cloudspace.update(**data)

    def applyConfig(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.applyConfig(cloudspaceId=cloudspaceId)

    def delete(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.delete(cloudspaceId=cloudspaceId)

    def deletePortForward(self, cloudspaceId, publicIp, publicPort, protocol):
        return self._api.cloudbroker.cloudspace.deletePortForward(
            cloudspaceId=cloudspaceId,
            publicIp=publicIp,
            publicPort=publicPort,
            protocol=protocol,
        )

    def deleteUser(self, cloudspaceId, username, recursivedelete=False):
        return self._api.cloudbroker.cloudspace.deleteUser(
            cloudspaceId=cloudspaceId,
            username=username,
            recursivedelete=recursivedelete,
        )

    def deployVFW(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.deployVFW(cloudspaceId=cloudspaceId)

    def moveVirtualFirewallToFirewallNode(self, cloudspaceId, targetNid):
        return self._api.cloudbroker.cloudspace.moveVirtualFirewallToFirewallNode(
            cloudspaceId=cloudspaceId, targetNid=targetNid
        )

    def destroy(self, cloudspaceId, accountId, **kwargs):
        reason = kwargs.get("reason", utils.random_string())
        return self._api.cloudbroker.cloudspace.destroy(
            accountId=accountId, cloudspaceId=cloudspaceId, reason=reason
        )

    def destroyCloudSpaces(self, cloudspaceIds, **kwargs):
        reason = kwargs.get("reason", utils.random_string())
        return self._api.cloudbroker.cloudspace.destroyCloudSpaces(
            cloudspaceIds=cloudspaceIds, reason=reason
        )


    def getVFW(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.getVFW(cloudspaceId=cloudspaceId)

    def removeIP(self, cloudspaceId, ipaddress):
        return self._api.cloudbroker.cloudspace.removeIP(
            cloudspaceId=cloudspaceId, ipaddress=ipaddress
        )

    def startVFW(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.startVFW(cloudspaceId=cloudspaceId)

    def stopVFW(self, cloudspaceId):
        return self._api.cloudbroker.cloudspace.stopVFW(cloudspaceId=cloudspaceId)

    def resetVFW(self, cloudspaceId, resettype):
        return self._api.cloudbroker.cloudspace.resetVFW(
            cloudspaceId=cloudspaceId, resettype=resettype
        )
