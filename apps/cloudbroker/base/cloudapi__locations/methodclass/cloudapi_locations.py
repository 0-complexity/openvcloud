from JumpScale import j
from cloudbrokerlib.baseactor import BaseActor


class cloudapi_locations(BaseActor):
    def list(self, **kwargs):
        """
        List all locations

        :return list with every element containing details of a location as a dict
        """
        return self.models.location.search({})[1:]

    def getUrl(self, **kwargs):
        """
        Get the portal url

        :return protal url
        """
        return self.config.get("portalurl")
