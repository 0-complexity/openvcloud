[actor] @dbtype:mem,osis
    """
    API Actor api, this actor is the final api a enduser uses to manage his resources
    """

    method:list
        """
        List the created disks belonging to an account
        """
        var:accountId int,,id of accountId the disks belongs to
        var:type str,,type of the disks @tags: optional
        result:list, list with every element containing details of a disk as a dict

    method:get
        """
        Get disk details
        """
        var:diskId int,, id of the disk
        result:dict, dict with the disk details


    method:limitIO
        """
        Limit IO for a certain disk
        total and read/write options are not allowed to be combined
        see http://libvirt.org/formatdomain.html#elementsDisks iotune section for more details
        """
        var:diskId int,, Id of the disk to limit
        var:iops int,, alias for total_iops_sec for backwards compatibility @optional
        var:total_bytes_sec int,, ... @optional
        var:read_bytes_sec int,, ... @optional
        var:write_bytes_sec int,, ... @optional
        var:total_iops_sec int,, ... @optional
        var:read_iops_sec int,, ... @optional
        var:write_iops_sec int,, ... @optional
        var:total_bytes_sec_max int,, ... @optional
        var:read_bytes_sec_max int,, ... @optional
        var:write_bytes_sec_max int,, ... @optional
        var:total_iops_sec_max int,, ... @optional
        var:read_iops_sec_max int,, ... @optional
        var:write_iops_sec_max int,, ... @optional
        var:size_iops_sec int,, ... @optional
        result:bool

    method:delete
        """
        Delete a disk
        """
        var:diskId int,, id of disk to delete
        var:detach bool,,detach disk from machine first @optional
        var:permanently bool,False, whether to completly delete the disk, works only with non attached disks @optional
        result: bool, True if disk was deleted successfully

    method:create
        """
        Create a disk
        """
        var:accountId int,,id of the account
        var:gid int,,id of the grid
        var:name str,,name of disk
        var:description str,,description of disk
        var:size int,10,size in GBytes, default is 0 @optional
        var:type str,B, (B;D;T)  B=Boot;D=Data;T=Temp
        var:ssdSize int,0,size in GBytes default is 0 @optional
        var:iops int,2000,max IOPS disk can perform defaults to 2000 @optional
        result:int, the id of the created disk

    method:resize
        """
        Resize disk
        Returns 200 if disk is resized online, else will return 202, in that case please stop and start your machine after changing the disk size, for your changes to be reflected.
        """
        var:diskId int,, Id of the disk to resize
        var:size int,, New size of the disk in GB
        result:str, return code of the operation

    method:restore
        """
        Restore a deleted unattached diskId
        """
        var:diskId int,, Id of the disk to restore
        var:reason str,, reason for restoring the disk
        result:bool, True if disk is restored

    method:deleteDisks
        """
        Delete multiple disks permanently
        """
        var:diskIds list(int),, list of disk ids to delete
        var:reason str,, reason for deleting the disks
        var:permanently bool,False, whether to completly delete the disks, works only with non attached disks @optional
        result:bool, True if disks are deleted