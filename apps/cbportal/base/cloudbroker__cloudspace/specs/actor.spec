[actor] @dbtype:mem,fs
    """
    Operator actions to perform interventions on cloudspaces
    """
    method:destroy
        """
        destroy a cloudspace
        If permanently is true, destroys its machines, vfws and routeros
        Otherwise it is possible to restore the cloudspace along with its machines again during the retention period
        Returns 200 if cloudspace is deleted or was already deleted or never existed
        """
        var:cloudspaceId str,,ID of cloudspace
        var:permanently bool,False, whether to completly delete the cloudspace @optional
        var:reason str,, reason for destroying the cloudspace

    method:moveVirtualFirewallToFirewallNode
        """
        move the virtual firewall of a cloudspace to a different firewall node
        """
        var:cloudspaceId int,, id of the cloudspace
        var:targetNid int,, name of the firewallnode the virtual firewall has to be moved to @optional


    method:migrateCloudspace
        """
        Migrate vfw from another grid
        """
        var:accountId int,,Account the cloudspace should be migrated in
        var:cloudspace obj,,Sourcecloudspace you want to migrate
        var:vfw obj,, Source VFW
        var:sourceip str,,sourceip ip from where to migrate
        var:gid int,,Grid id cloudspace belongs to

    method:resetVFW
        """
        Reset VFW
        """
        var:cloudspaceId int,, id of the cloudspace
        var:resettype str,,either factory or restore

    method:restore
        """
        Restore a deleted cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:reason str,, reason for restoring the cloudspace
    
    method:applyConfig
        """
        Apply vfw rules
        """
        var:cloudspaceId int,, id of the cloudspace

    method:getVFW
        """
        Get VFW info
        """
        var:cloudspaceId int,, id of the cloudspace

    method:deployVFW
        """
        Deploy VFW
        """
        var:cloudspaceId int,, id of the cloudspace
        var:type str,routeros,Type of router for cloudspace

    method:startVFW
        """
        Start VFW
        """
        var:cloudspaceId int,, id of the cloudspace

    method:changeRouterType
        """
        Change the routertype of your cloudspace
        """
        var:cloudspaceId int,, id of the cloudspace
        var:routertype str,, routertype to change to vgw or routeros
        var: force bool,, whether to check routeros first or not @optional


    method:stopVFW
        """
        Stop VFW
        """
        var:cloudspaceId int,, id of the cloudspace

    method:create
        """
        Create a cloudspace for given account
        Setting a cloud unit maximum to -1 or empty will not put any restrictions on the resource
        """
        var:accountId int,, name of account to create space for
        var:location str,, location key where the space should be created
        var:name str,, name of space to create @tags validator:name
        var:access str,, username which will have full access to this space(current logged in user if left empty) @optional
        var:maxMemoryCapacity float,-1, max size of memory in GB @optional
        var:maxVDiskCapacity int,-1, max size of aggregated vdisks in GB @optional
        var:maxCPUCapacity int,-1, max number of cpu cores @optional
        var:maxNetworkPeerTransfer int,-1, max sent/received network transfer peering @optional
        var:maxNumPublicIP int,-1, max number of assigned public IPs @optional
        var:externalnetworkId int,, Id of external network to connect to @optional
        var:allowedVMSizes list(int),, allowed sizes per cloudspace @optional
        var:privatenetwork str,192.168.103.0/24,private network to use for cloudspace eg. 192.168.103.0/24 @optional
        var:type str,routeros,Type of router to use for the cloudspace @optional

    method:update
        """
        Update cloudspace.
        Setting a cloud unit maximum to -1 or empty will not put any restrictions on the resource
        """"
        var:cloudspaceId int,,ID of cloudspace
        var:name str,, Display name
        var:maxMemoryCapacity float,, max size of memory in GB @optional
        var:maxVDiskCapacity int,, max size of aggregated vdisks in GB @optional
        var:maxCPUCapacity int,, max number of cpu cores @optional
        var:maxNetworkPeerTransfer int,, max sent/received network transfer peering @optional
        var:maxNumPublicIP int,, max number of assigned public IPs @optional
        var:allowedVMSizes list(int),, allowed sizes per cloudspace @optional

    method:destroyVFW
        """
        Destroy VFW of this cloudspace
        """
        var:cloudspaceId int,,Id of the cloudspace

    method:addUser
        """
        Give a user access rights.
        """"
        var:cloudspaceId int,,Id of the cloudspace
        var:username str,,name of the user to be given rights
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin

    method:deleteUser
        """
        Delete user from account.
        """"
        var:cloudspaceId int,,Id of the cloudspace
        var:username str,,name of the user to be removed
        var:recursivedelete bool,, recursively delete access rights from owned cloudspaces and vmachines

    method:deletePortForward
        """
        Deletes a port forwarding rule for a machine
        """
        var:cloudspaceId int,, ID of cloudspace
        var:publicIp str,,Portforwarding public ip
        var:publicPort int,,Portforwarding public port
        var:proto str,,Portforwarding protocol

    method:destroyCloudSpaces
        """
        Destroy a group of cloud spaces
        """
        var:cloudspaceIds list(int),, IDs of cloudspaces
        var:reason str,, reason for deletion
        var:permanently bool ,, whether to completly destroy cloudspaces or not @optional
