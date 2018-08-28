[actor] @dbtype:mem,osis
    """
    API Actor api, this actor is the final api a enduser uses to manage his resources
    """

    method:create
        """
        Create a machine based on the available sizes, in a certain cloud space
        The user needs write access rights on the cloud space
        """
        var:cloudspaceId int,,id of cloud space in which we want to create a machine
        var:name str,,name of machine @tags validator:name
        var:description str,,optional description @tags: optional
        var:sizeId int,,id of the specific size @optional 
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        var:imageId int,, id of the specific image
        var:disksize int,, size of base volume
        var:datadisks list(int),, list of extra data disks in gigabytes  @optional
        var:userdata obj,,Object or string @optional
        result:bool


    method:list
        """
        List the deployed machines in a space. Filtering based on status is possible
        """
        var:cloudspaceId int,,id of cloud space in which machine exists @tags: optional
        result:list

    method:get
        """
        Get information from a certain object.
        This contains all information about the machine.
        """
        var:machineId int,, id of machine
        result: bool

    method:delete
        """
        Delete a machine
        """
        var:machineId int,, id of the machine
        var:permanently bool,False, whether to completly delete the machine @optional
        result: bool

    method:update
        """
        Change basic properties of a machine
        Name, description can be changed with this action.
        """
        var:machineId int,, id of the machine
        var:name str,, name of the machine @tags: optional validator:name
        var:description str,, description of the machine @tags: optional

    method:start
        """
        Start the machine
        """
        var:machineId int,, id of the machine
        var:diskId int,, Disk id of CD-ROM to boot @optional
        result:bool

    method:stop
        """
        Stop the machine
        """
        var:machineId int,, id of the machine
        var:force bool,False,force machine shutdown @optional
        result:bool

    method:reboot
        """
        Reboot the machine
        """
        var:machineId int,, id of the machine
        result:bool

    method:reset
        """
        Reset the machine, force reboot
        """
        var:machineId int,, id of the machine
        result:bool

    method:pause
        """
        Pause the machine
        """
        var:machineId int,, id of the machine
        result:bool

    method:resume
        """
        Resume the machine
        """
        var:machineId int,, id of the machine
        result:bool

    method:restore
        """
        Restore a deleted machine
        """
        var:machineId int,, id of the machine
        var:reason str,,Reason
        result:bool

    method:addDisk
        """
        Create and attach a disk to the machine
        """
        var:machineId int,,id of the machine
        var:diskName str,,name of disk
        var:description str,,optional description
        var:size int,10,size in GByte
        var:type str,B, (B;D;T) B=Boot;D=Data;T=Temp
        var:ssdSize int,0,size in GBytes default is 0 @optional
        var:iops int,2000, total disk iops per sec @optional
        result:int, id of the disk

    method:attachDisk
        """
        Attach a disk to the machine
        """
        var:machineId int,, id of the machine
        var:diskId int,,id of disk to attach
        result:bool, True if disk was attached successfully

    method:detachDisk
        """
        Detach a disk from the machine
        """
        var:machineId int,, id of the machine
        var:diskId int,,id of disk to detach
        result:bool, True if disk was detached successfully

    method:snapshot
        """
        Take a snapshot of the machine
        """
        var:machineId int,,id of machine to snapshot
        var:name str,, name to give snapshot @tags validator:name
        var:force bool,False,force create a new snapshot if existing snapshot with the same name @optional
        result:dict diskguid:snapshotguid

    method:listSnapshots
        """
        List the snapshots of the machine
        """
        var:machineId int,, id of the machine
        result:list, list with the available snapshots

    method:deleteSnapshot
        """
        Delete a snapshot of the machine
        """
        var:machineId int,, id of the machine
        var:epoch int,, epoch time of snapshot @optional
        var:name str,, name of snapshot @optional
        result:bool

    method:rollbackSnapshot
        """
        Rollback a snapshot of the machine
        """
        var:machineId int,, id of the machine
        var:epoch int,, epoch time of snapshot @optional
        var:name str,, name of snapshot @optional
        result:str

    method:createTemplate
        """
        Create a template form a machine
        """
        var:machineId int,, id of the machine
        var:templateName str,, name of the template
        var:callbackUrl str,, callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion. @optional
        result:bool, True if template was created

    method:importOVF
        """
        Import a machine from owncloud(ovf)
        """
        var:link str,, WebDav link to owncloud
        var:username str,, WebDav Username
        var:passwd str,, WebDav Password
        var:path str,, Path to ovf file in WebDav share
        var:cloudspaceId int,, id of the cloudspace in which the vm should be created
        var:name str,,name of machine @tags validator:name
        var:description str,,optional description @tags: optional
        var:sizeId int,,id of the specific size @optional 
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        var:callbackUrl str,, callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion. @optional

    method:exportOVF
        """
        Export a machine with it's disks to owncloud(ovf)
        """
        var:link str,, WebDav link to owncloud
        var:username str,, WebDav Username
        var:passwd str,, WebDav Password
        var:path str,, Path to ovf file in WebDav share
        var:machineId int,, id of the machine to export
        var:callbackUrl str,, callback url so that the API caller can be notified. If this is specified the G8 will not send an email itself upon completion. @optional

    method:getConsoleUrl
        """
        Get url to connect to console
        """
        var:machineId str,, id of the machine to connect to the console
        result:str, one time url used to connect to the console


    method:resize
        """
        Change the size of a machine
        Returns status code 200 with response true if size has been updated live on the machine
        Returns status code 202 with response false if the size could not be applied live and required a stop/start of the machine
        """
        var:machineId int,, id of machine to resize
        var:sizeId int,,id of the specific size @optional 
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        result:bool

    method:clone
        """
        Clone the machine
        """
        var:machineId int,,id of the machine to clone
        var:name str,, name of the cloned machine @tags validator:name
        var:cloudspaceId int,, optional id of the cloudspace in which the machine should be put @optional
        var:snapshotTimestamp int,, optional snapshot timestap to base the clone upon @optional
        var:snapshotname str,, optional snapshot name to base the clone upon @optional
        result:int, id of the new cloned machine

    method:getHistory
        """
        Get machine history
        """
        var:machineId int,,id of the machine
        var:size int,, number of entries to return
        result:list, list of the history of the machine

    method:addUser
        """
        Give a registered user access rights
        """
        var:machineId int,,  id of the machine
        var:userId str,, username or emailaddress of the user to grant access
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        result:bool, True if user was added successfully

    method:deleteUser
        """
        Revoke user access from the vmachine
        """
        var:machineId int,, id of the machine
        var:userId str,, id or emailaddress of the user to remove
        result:bool, True if user access was revoked from machine

    method:updateUser
        """
        Update user access rights. Returns True only if an actual update has happened.
        """
        var:machineId int,, id of the machineId
        var:userId str,, userid/email for registered users or emailaddress for unregistered users
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin
        result:bool, True if user access was updated successfully

    method:attachExternalNetwork
        """
        Attach an external network to the machine
        """
        var:machineId int,, id of the machine
        var:externalNetworkId int,, optional external network id to take ip address from. If omitted will search for available network @optional
        result:bool, True if an external network was attached to the machine

    method:detachExternalNetwork
        """
        Detach an external network from the machine
        """
        var:machineId int,, id of the machine
        var:externalNetworkId int,, external network id. If omitted all external networks will be detached @optional
        result:bool, True if the external network was detached from the machine

    method:listExternalNetworks
        """
        List the external networks that the machine is attached to
        """
        var:machineId int,, id of the machine
        result:list, list of external network ids
