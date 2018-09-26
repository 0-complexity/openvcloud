[actor] @dbtype:mem,osis
    """
    API Actor api for managing cloudspaces, this actor is the final api a enduser uses to manage cloudspaces
    """
    method:create
        """
        Create an extra cloudspace
        Setting a cloud unit maximum to -1 or empty will not put any restrictions on the resource
        """
        var:accountId int,,id of acount this cloudspace belongs to
        var:location str,, location code for the cloudspace
        var:name str,,name of space to create @tags validator:name
        var:access str,,username of a user which has full access to this space @tags validator:name
        var:maxMemoryCapacity float,-1, max size of memory in GB @optional
        var:maxVDiskCapacity int,-1, max size of aggregated vdisks in GB @optional
        var:maxCPUCapacity int,-1, max number of cpu cores @optional
        var:maxNetworkPeerTransfer int,-1, max sent/received network transfer peering @optional
        var:maxNumPublicIP int,-1, max number of assigned public IPs @optional
        var:externalnetworkId int,, id of externalnetwork to connect to @optional
        var:allowedVMSizes list(int),, allowed sizes per cloudspace @optional
        var:privatenetwork str,192.168.103.0/24,Private network CIDR eg. 192.168.103.0/24 @optional
        var:type str,zgw,Type of cloudspace router @optional
        result:int, id of created cloudspace

    method:deploy
        """
        Create VFW for cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        result:str, status of deployment

    method:delete
        """
        Delete the cloudspace
        Returns 200 if cloudspace is deleted or was already deleted or never existed
        """
        var:cloudspaceId int,, id of the cloudspace
        var:permanently bool,False, whether to completly delete the cloudspace @optional
        result:bool, True if deletion was successful

    method:disable
        """
        Disable the cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:reason str,, reason for disabling
        result:bool, True if disabling was successful

    method:enable
        """
        Enable the cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:reason str,, reason for enabling
        result:bool, True if enabling was successful

    method:list
        """
        List all cloudspaces the user has access to
        """
        var:includedeleted bool,false, included deleted cloud spaces @optional
        result:[], list with every element containing details of a cloudspace as a dict

    method:get
        """
        Get cloudspace details
        """
        var:cloudspaceId int,, id of the cloudspace
        result:dict, dict with cloudspace details

    method:addAllowedSize
        """
        Add allowed size for a cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:sizeId int,, id of the required size to be added
        result:bool, True if size is added

    method:restore
        """
        Restore a deleted cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:reason str,, reason for restoring the cloudspace

    method:removeAllowedSize
        """
        Remove allowed size for a cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:sizeId int,, id of the required size to be removed
        result:bool, True if size is removed

    method:update
        """
        Update the cloudspace name and capacity parameters
        Setting a cloud unit maximum to -1 or empty will not put any restrictions on the resource
        """
        var:cloudspaceId int,, id of the cloudspace
        var:name str,, name of the cloudspace @optional @tags validator:name
        var:maxMemoryCapacity float,, max size of memory in GB @optional
        var:maxVDiskCapacity int,, max size of aggregated vdisks in GB @optional
        var:maxCPUCapacity int,, max number of cpu cores @optional
        var:maxNetworkPeerTransfer int,, max sent/received network transfer peering @optional
        var:maxNumPublicIP int,, max number of assigned public IPs @optional
        var:allowedVMSizes list(int),, allowed sizes per cloudspace @optional
        result:bool, True if cloudspace was updated

    method:addUser
        """
        Give a registered user access rights
        """
        var:cloudspaceId int,, id of the cloudspace
        var:userId str,, username or emailaddress of the user to grant access
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        result:bool, True if user was added successfully

    method:updateUser
        """
        Update user access rights. Returns True only if an actual update has happened.
        """
        var:cloudspaceId int,, id of the cloudspace
        var:userId str,, userid/email for registered users or emailaddress for unregistered users
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        result:bool, True if user access was updated successfully

    method:deleteUser
        """
        Revoke user access from the cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:userId str,, id or emailaddress of the user to remove
        var:recursivedelete bool,False, recursively revoke access rights from related vmachines @optional
        result: bool, True if user access was revoked from cloudspace

    method:getDefenseShield
        """
        Get information about the defense shield
        """
        var:cloudspaceId int,, id of the cloudspace
        result: dict, dict with defense shield details

    method:getOpenvpnConfig @method:get,post
        """
        Get OpenVPN config file (in zip format) for specified cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        result:str, binary zip file

    method:executeRouterOSScript
        """
        Execute a script on the routeros of the cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:script str,, script to execute
        result:bool
