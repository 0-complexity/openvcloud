from JumpScale import j

class cloudapi_users(object):
    """
    User management

    """
    def __init__(self):

        self._te = {}
        self.actorname = "users"
        self.appname = "cloudapi"
        self._cb = None
        self._models = None
        self.libvirt_actor = j.apps.libcloud.libvirt


    @property
    def cb(self):
        if not self._cb:
            self._cb = j.apps.cloud.cloudbroker
        return self._cb

    @property
    def models(self):
        if not self._models:
            self._models = self.cb.extensions.imp.getModel()
        return self._models

    def authenticate(self, username, password, **kwargs):
        """
        The function evaluates the provided username and password and returns a session key.
        The session key can be used for doing api requests. E.g this is the authkey parameter in every actor request.
        A session key is only vallid for a limited time.
        param:username username to validate
        param:password password to validate
        result str,,session
        """
        ctx = kwargs['ctx']
        if j.core.portal.active.auth.authenticate(username, password):
            session = ctx.env['beaker.get_session']() #create new session
            session['user'] = username
            session.save()
            return session.id
        else:
            ctx.start_response('401 Unauthorized', [])
            return 'Unauthorized'
    def get(self, username, **kwargs):
        """
        Get information of a existing username based on username id
        param:username username of the user
        result:
        """
        user = j.core.portal.active.auth.getUserInfo(username)
        if user:
            return {'username':user.id, 'emailaddresses':user.emails}
        else:
            ctx = kwargs['ctx']
            ctx.start_response('404 Not Found', [])
            return 'User not found'
    
    def _send_mail(self):
        import smtplib

        fromaddr = 'support@mothership1.com'
        toaddrs  = 'support@mothership1.com'
        
        msg = '''
Subject: testin'...
        
There was a terrible error that occured and I wanted you to know!
'''


        # Credentials (if needed)
        username = 'support@mothership1.com'
        password = ''

        # The actual mail send
        server = smtplib.SMTP('smtp.gmail.com:587')
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(username,password)
        server.sendmail(fromaddr, toaddrs, msg)
        server.quit()

    def register(self, username, emailaddress, password, **kwargs):
        """
        Register a new user, a user is registered with a login, password and a new account is created.
        param:username unique username for the account
        param:emailaddress unique emailaddress for the account
        param:password unique password for the account
        result bool
        """
        ctx = kwargs['ctx']
        if j.core.portal.active.auth.userExists(username):
            ctx.start_response('409 Conflict', [])
            return 'User already exists'
        else:
            #During beta, generate a random password
            import string, random
            password = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12))
            
            j.core.portal.active.auth.createUser(username, password, emailaddress, username, None)
            account = self.models.account.new()
            account.name = username
            ace = account.new_acl()
            ace.userGroupId = username
            ace.type = 'U'
            ace.right = 'CXDRAU'
            accountid = self.models.account.set(account)[0]
            #networkid = self.libvirt_actor.getFreeNetworkId()
            #publicipaddress = self.cb.extensions.imp.getPublicIpAddress(networkid)
            #cs = self.models.cloudspace.new()
            #cs.name = 'default'
            #cs.accountId = accountid
            #cs.networkId = networkid
            #cs.publicipaddress = publicipaddress
            #ace = cs.new_acl()
            #ace.userGroupId = username
            #ace.type = 'U'
            #ace.right = 'CXDRAU'
            #self.models.cloudspace.set(cs)
            return True
