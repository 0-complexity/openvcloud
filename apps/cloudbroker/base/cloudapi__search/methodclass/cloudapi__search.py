from JumpScale import j
from cloudbrokerlib import authenticator, resourcestatus
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import resourcestatus

class cloudapi_search(BaseActor):
    """
    API Actor api for search requests

    """

    def __init__(self):
        super(cloudapi_search, self).__init__()
        self.systemodel = j.clients.osis.getNamespace('system')

    #@authenticator.auth(acl={'account': set('U')})
    def search(self, search, filter=[], **kwargs):
        """
        Implements search function in OVC

        :param search: search request containing a name/id or any object on OVC
        :param filter: filters for search
        """


        filters = {'status': {'$nin': resourcestatus.Account.INVALID_STATES}}
        ctx = kwargs['ctx']
        user = ctx.env['beaker.session']['user']
        fields = ['id', 'name', 'acl', 'creationTime', 'updateTime']
        q = {'acl.userGroupId': user, 'status': {'$in': [resourcestatus.Account.DISABLED, resourcestatus.Account.CONFIRMED]}}
        query = {'$query': q, '$fields': fields}
        accounts = self.models.account.search(query)[1:]
        return accounts

