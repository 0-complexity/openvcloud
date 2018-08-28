[actor] @dbtype:mem,fs
    """
    machine manager
    """

    method:get
        """
        gets machine json object.
        """
        var:machineId int,, ID of machine
        result:json

    method:create
        """
        Create a machine based on the available sizes, in a certain space.
        The user needs write access rights on the space.
        """
        var:cloudspaceId int,,id of space in which we want to create a machine
        var:name str,,name of machine @tags validator:name
        var:description str,,optional description @tags: optional
        var:sizeId int,,id of the specific size @optional
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        var:imageId int,, id of the specific image
        var:disksize int,, size of base volume
        var:datadisks list(int),, list of data disk sizes in gigabytes @optional
        result:bool

    method:createOnStack
        """
        Create a machine on a specific stackid
        """
        var:cloudspaceId int,,id of space in which we want to create a machine
        var:name str,,name of machine @tags validator:name
        var:description str,,optional description @tags: optional
        var:sizeId int,,id of the specific size @optional
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        var:imageId int,, id of the specific image
        var:disksize int,, size of base volume
        var:stackid int,, id of the stack
        var:datadisks list(int),, list of data disk sizes in gigabytes @optional
        var:userdata obj,,Object or string @optional
        result:bool
    
    method:prepareForMigration
        """
        Prepate a target vm for migrating to
        """
        var:cloudspaceId int,,id of space in which we want to migrate the vm in
        var:machine obj,,Machine object containing info for target
        result:obj


    method:stop
        """
        Stops a machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason

    method:start
        """
        Starts a deployed machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason
        var:diskId int,,CD-ROM diskId to boot from @optional

    method:restore
        """
        Restore a deleted machine
        """
        var:machineId int,, id of the machine
        var:reason str,,Reason
        result:bool
    
    method:reboot
        """
        Reboots a deployed machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason

    method:pause
        """
        Pauses a deployed machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason

    method:resume
        """
        Resumes a deployed paused machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason

    method:snapshot
        """
        Takes a snapshot of a deployed machine
        """
        var:machineId int,,Machine id
        var:snapshotName str,,Snapshot name @tags validator:name
        var:reason str,,Reason

    method:rollbackSnapshot
        """
        Rolls back a machine snapshot
        """
        var:machineId int,,Machine id
        var:epoch int,,Snapshot timestamp
        var:reason str,,Reason

    method:deleteSnapshot
        """
        Deletes a machine snapshot
        """
        var:machineId int,,Machine id
        var:epoch int,,Snapshot timestamp
        var:reason str,,Reason

    method:clone
        """
        Clones a machine
        """
        var:machineId int,,Machine id
        var:cloneName str,,Clone name @tags validator:name
        var:reason str,,Reason

    method:destroy
        """
        Destroys a machine
        """
        var:machineId int,,Machine id
        var:reason str,,Reason
        var:permanently bool,False, whether to completly delete the machine @optional

    method:moveToDifferentComputeNode
        """
        Live-migrates a machine to a different CPU node.
        If no targetnode is given, the normal capacity scheduling is used to determine a targetnode
        """
        var:machineId int,,Machine id
        var:reason str,,Reason
        var:targetStackId int,, Name of the compute node the machine has to be moved to @optional
        var:force bool,,force move of machine even if storage is busy

#    method:export
#        """
#        Create a export/backup of a machine
#        """
#        var:machineId int,, id of the machine to backup
#        var:name str,, Usefull name for this backup
#        var:backuptype str,, Type e.g raw, condensed
#        var:storage str,, Type of storage used. e.g S3 or RADOS.
#        var:bucketname str,,bucket name
#        var:host str,, host to export(if s3) @tags: optional
#        var:aws_access_key str,,s3 access key @tags: optional
#        var:aws_secret_key str,,s3 secret key @tags: optional
#        result:jobid

    method:tag
        """
        Adds a tag to a machine, useful for indexing and following a (set of) machines
        """
        var:machineId int,, id of the machine to tag
        var:tagName str,, tag

    method:untag
        """
        Removes a specific tag from a machine
        """
        var:machineId int,, id of the machine to untag
        var:tagName str,, tag

#    method:listExports
#        """
#        List of created exports
#        """
#        var:status str,,status of the backup @tags: optional
#        var:machineId int,,id of the machine @tags: optional
#        result: list of created exports

    method:list
        """
        List the undestroyed machines based on specific criteria
        At least one of the criteria needs to be passed
        """
        var:tag str,, a specific tag @optional
        var:computeNode str,, name of a specific computenode @optional
        var:cloudspaceId int,, specific cloudspace @optional


#    method:stopForAbusiveResourceUsage
#        """
#        If a machine is abusing the system and violating the usage policies it can be stopped using this procedure.
#        A ticket will be created for follow up and visibility, the machine stopped, the image put on slower storage and the ticket is automatically closed if all went well.
#        Use with caution!
#        """
#        var:accountId int,,Account name, extra validation for preventing a wrong machineId
#        var:machineId int,,Id of the machine
#        var:reason str,,Reason
#
#    method:backupAndDestroy
#        """
#        * Create a ticket
#        * Call the backup method
#        * Destroy the machine
#        * Close the ticket
#        Use with caution!
#        """
#        var:accountId int,,Account name, extra validation for preventing a wrong machineId
#        var:machineId int,,Id of the machine
#        var:reason str,,Reason

    method:listSnapshots
        """
        list snapshots of a machine
        """
        var:machineId int,, ID of machine
        result:bool

    method:getHistory
        """
        get history of a machine
        """
        var:machineId int,, ID of machine
        result:bool

    method:listPortForwards
        """
        portforwarding of a machine
        """
        var:machineId int,, ID of machine
        var:result json,,

    method:createPortForward
        """
        Creates a port forwarding rule for a machine
        """
        var:machineId int,, ID of machine
        var:localPort int,,Source port
        var:destPort int,,Destination port
        var:proto str,,Protocol

    method:deletePortForward
        """
        Deletes a port forwarding rule for a machine
        """
        var:machineId int,, ID of machine
        var:publicIp str,,Portforwarding public ip
        var:publicPort int,,Portforwarding public port
        var:proto str,,Portforwarding protocol


    method:addDisk
        """
        Adds a disk to a deployed machine
        """
        var:machineId int,, ID of machine
        var:diskName str,,Name of the disk @tags validator:name
        var:description str,,Description
        var:size int,,size in GByte default=10 @tags: optional
        var:iops int,2000, total disk iops per sec @optional

    method:deleteDisk
        """
        Deletes a disk from a deployed machine
        """
        var:machineId int,, ID of machine
        var:diskId int,, ID of disk

    method:createTemplate
        """
        Create template from a machine
        """
        var:machineId int,, ID of machine
        var:templateName str,, Name of the template @tags validator:name
        var:reason str,,Reason

    method:updateMachine
        """
        Updates machine description
        """
        var:machineId int,, ID of machine
        var:name str,, new name
        var:description str,, new description
        var:reason str,,Reason

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
        var:externalNetworkId int,, optional external network id. If omitted all external networks will be detached @optional
        result:bool, True if the external network was detached from the machine

    method:listExternalNetworks
        """
        List the external networks that the machine is attached to
        """
        var:machineId int,, id of the machine
        result:list, list of external network ids

    method:addUser
        """
        Give a user access rights.
        """"
        var:machineId int,,Id of the machine
        var:username str,,name of the user to be given rights
        var:accesstype str,, 'R' for read only access, 'RCX' for Write and 'ARCXDU' for Admin

    method:deleteUser
        """
        Delete user from account.
        """"
        var:machineId int,,Id of the machine
        var:username str,,name of the user to be removed
    method:resize
        """
        Change memory and vcpu from machine
        """
        var:machineId int,, ID of machine
        var:sizeId int,,id of the specific size @optional
        var:memory int,,amount of memory to provide @optional
        var:vcpus int,,number of vcpus to provide @optional
        result:bool

    method:startMachines
        """
        Starts a deployed machines
        """
        var:machineIds list(int),,Machine ids
        var:reason str,,Reason

    method:stopMachines
        """
        Stops the running machines
        """
        var:machineIds list(int),,Machine ids
        var:reason str,,Reason

    method:rebootMachines
        """
        Reboots running machines
        """
        var:machineIds list(int),,Machine ids
        var:reason str,,Reason

    method:destroyMachines
        """
        Destroys machines
        """
        var:machineIds list(int),,Machine ids
        var:reason str,,Reason
        var:permanently bool,False, whether to completly delete the machines @optional
