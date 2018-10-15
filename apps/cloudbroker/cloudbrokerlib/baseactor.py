from . import cloudbroker
from JumpScale.portal.portal import exceptions
from JumpScale.portal.portal.PortalClient2 import ApiError

from JumpScale import j


class BaseActor(object):
    def __init__(self):
        self.cb = cloudbroker.CloudBroker()
        self.models = cloudbroker.models
        self.sysmodels = cloudbroker.sysmodels
        self.config = j.core.config.get('openvcloud', 'main')


def wrap_remote(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ApiError as e:
            ctype = e.response.headers.get("Content-Type", "text/plain")
            headers = [("Content-Type", ctype)]
            statuscode = e.response.status_code or 500
            raise exceptions.BaseError(statuscode, headers, e.response.content)

    return wrapper
