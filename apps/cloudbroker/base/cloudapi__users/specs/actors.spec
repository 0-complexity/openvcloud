[actor] @dbtype:mem,osis
	"""
	User management
	"""

	method:authenticate @noauth
	    """
	    The function evaluates the provided username and password and returns a session key.
	    The session key can be used for doing api requests. E.g this is the authkey parameter in every actor request.
	    A session key is only vallid for a limited time.
	    """

	    var:username str,,username to validate
	    var:password str,,password to validate
	    result:str,,session key.

	method:register @noauth
	    """
	    Register a new user, a user is registered with a login, password and a new account is created.
	    """
	    var:username str,,unique username for the account
	    var:emailaddress str,,unique emailaddress for the account
	    var:password str,,unique password for the account
	    var:user str,,name for the account
	    var:company str,,name of the company
	    var:companyurl str,,url of the main website
	    var:location str,,location
	    var:promocode str,,promocode @optional
	    result:bool

	method:get
	    """
	    Get information of a existing username based on username id
	    """
        var:username str,,username of the user
        result:dict,,user information.

	method:updatePassword
	    """
	    Change user password
	    """
        var:oldPassword str,,oldPassword of the user
        var:newPassword str,,newPassword of the user
        result:dict,,user information.

    method:sendResetPasswordLink @noauth
	    """
	    Sends a reset password link to the supplied email address
	    """
	    var:emailaddress str,,unique emailaddress for the account
	    result:bool

    method:getResetPasswordInformation @noauth
        """
        Retrieve information about a password reset token (if still valid)
        """
        var:resettoken str,, password reset token
        result:bool

    method:resetPassword @noauth
        """
        Resets a password
        """
        var:resettoken str,, password reset token
        var:newpassword str,, new password
        result:bool

    method:validate @noauth
        """
        Validates a newly registered user
        """
        var:validationtoken str,, token generated at usercreation and sent via email
        result:bool
