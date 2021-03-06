from JumpScale import j
from JumpScale.portal.portal import exceptions
import json


class cloudbroker_health(object):
    """
    API Check status of grid
    """

    def status(self, **kwargs):
        """
        check status of grid
        result dict
        """
        resp = {}
        try:
            dbstate = j.core.portal.active.osis.getStatus()
            resp["mongodb"] = dbstate["mongodb"]
            resp["influxdb"] = dbstate["influxdb"]
        except Exception:
            resp["mongodb"] = False
            resp["influxdb"] = False

        resp["healtcheckalive"] = j.core.grid.healthchecker.fetchState() == "OK"

        if all(resp.values()):
            return resp
        else:
            raise exceptions.ServiceUnavailable(resp)
