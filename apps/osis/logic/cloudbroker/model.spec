
[rootmodel:VMachine] @dbtype:osis
    """
    """
    prop:id int,,
    prop:name str,,name as given by customer @index
    prop:descr str,,
    prop:sizeId int,,id of size used by machine, size is the cloudbroker size. @index
    prop:imageId int,,id of image used to create machine @index
    prop:dedicatedCU bool,False,if true the compute capacity will be dedicated
    prop:disks list(int),,List of id of Disk objects
    prop:nics list(Nic),,List of id Nic objects (network interfaces) attached to this vmachine
    prop:referenceId str,,name as used in hypervisor @index
    prop:accounts list(VMAccount),,list of machine accounts on the virtual machine
    prop:status str,,status of the vm (HALTED;INIT;RUNNING;TODELETE;SNAPSHOT;EXPORT;DESTROYED) @index
    prop:hostName str,,hostname of the machine as specified by OS; is name in case no hostname is provided @index
    prop:cpus int,1,number of cpu assigned to the vm
    prop:boot bool,True,indicates if the virtual machine must automatically start upon boot of host machine
    prop:hypervisorType str,VMWARE,hypervisor running this vmachine (VMWARE;HYPERV;KVM)
    prop:stackId int,,ID of the stack
    prop:acl list(ACE),,access control list @index
    prop:cloudspaceId int,,id of space which holds this vmachine @index
    prop:networkGatewayIPv4 str,,IP address of the gateway for this vmachine
    prop:referenceSizeId str,, reference to the size used on the stack
    prop:cloneReference int,, id to the machine on which this machine is based
    prop:clone int,, id of the clone
    prop:creationTime int,, epoch time of creation, in seconds @index
    prop:updateTime int,, epoch time of update, in seconds @index
    prop:deletionTime int,, epoch time of deletion, in seconds @index
    prop:memory int,, the amount of mmemory available to this machine
    prop:vcpus int,, the number of vcpus available to this machine 
    prop:type str,,Type of machine @index
    prop:tags str,, A tags string @index

[model:VMAccount] @dbtype:osis
    """
    Machine account on the virtual machine
    """
    prop:login str,,login name of the machine account
    prop:password str,,password of the machine account

[rootmodel:Account] @dbtype:osis
    """
    Account owner of cloudspaces
    """
    prop:id int,,
    prop:name str,,Name of account @index
    prop:acl list(ACE),, access control list @index
    prop:status str,, status of the account (UNCONFIRMED, CONFIRMED, DISABLED) @index
    prop:creationTime int,, epoch time of creation, in seconds @index
    prop:updateTime int,, epoch time of update, in seconds @index
    prop:deactivationTime int,, epoch time of the deactivation, in seconds
    prop:DCLocation str,, The preferred Datacenter Location for new cloudspaces
    prop:company str,, Company holding the account
    prop:companyurl str,, Website of the company holding the account
    prop:displayname str,, The name as the account should be displayed
    prop:resourceLimits dict(int),,int amount of max nr of units which can be used there
    prop:sendAccessEmails bool,True, if true sends emails when a user is granted access to resources

[model:ACE]
    """
    Access control list
    """
    prop:userGroupId str,,unique identification of user or group
    prop:type str,,user or group (U or G)
    prop:right str,,right string now RWD  (depending type of object this action can be anything each type of action represented as 1 letter)
    prop:status str,CONFIRMED, whether the user is still INVITED or has already CONFIRMED (registered) in the system
    prop:explicit bool,True, True if the permission is explicitly added 

[rootmodel:Image] @dbtype:osis
    """
    """
    prop:id int,,
    prop:gid int,,
    prop:name str,,name of the image @index
    prop:description str,,extra description of the image
    prop:UNCPath str,,location of the image (uncpath like used in pylabs); includes the login/passwd info
    prop:size int,, minimal disk size in Gigabyte @index
    prop:type str,, dot separated list of independant terms known terms are: tar;gz;sso e.g. sso dump inn tar.gz format would be sso.tar.gz  (always in lcas) @index
    prop:referenceId str,,Name of the image on stack
    prop:status str,, status of the image, e.g DISABLED/ENABLED/CREATING/DELETING @index
    prop:accountId int,,id of account to which this image belongs @index
    prop:acl list(ACE),,access control list
    prop:username str,, specific username for this image
    prop:password str,, specific password for this image
    prop:provider_name str,, provider name for this image openstack/libvirt, ...
    prop:bootType str,, image boot type e.g bios, uefi
    prop:deletionTime int,, epoch time of deletion, in seconds @index
    prop:hotResize bool,, Does image support hot resize?
    prop:url str,, url used to get/update the image
    prop:lastModified int,, last modified timestamp of the downloaded image

[rootmodel:DiskType] @dbtype:osis
    """
    """
    prop:id str,,
    prop:description str,, extra description of the type
    prop:vpool str,, which vpool this disktype relates to
    prop:cacheratio int,, disk cache ratio
    prop:snapshotable bool,, Does this disk type snapshotable?

[rootmodel:Stack] @dbtype:osis
    """
    """
    prop:id int,,
    prop:name str,,name as given by customer @index
    prop:descr str,,
    prop:login str,,login name if applicable
    prop:passwd str,,passwd if applicable
    prop:apikey str,,apikey if applicable
    prop:apiUrl str,,URL to communicate to the stack
    prop:type str,,Type of the stack, (OPENSTACK|CLOUDFRAMES|XEN SOURCE) @index
    prop:appId str,,application id if applicable
    prop:images list(int),,list of images ids supported by this resource model updated
    prop:referenceId str,,Optional reference id. @index
    prop:error int,,Track amount of errors happened
    prop:eco str,,ECO which put stack in error
    prop:gid int,,Grid id. @index
    prop:status str,,Indicates the current status of the stack. e.g DISABLED/ENABLED/MAINTENANCE @index
	prop:type str,,Indicates the type of stack [libvirt/openstack]

[rootmodel:Disk] @dbtype:osis
    """
    """
    prop:id int,,
    prop:name str,,name as given by customer
    prop:descr str,,
    prop:sizeMax int,,provisioned size of disk in MB @index
    prop:sizeUsed int,,used capacity of disk in MB
    prop:referenceId str,,name as used in hypervisor @index
    prop:realityDeviceNumber int,, Number a device gets after connect
    prop:status str,,status of the vm (ACTIVE;INIT;IMAGE) @index
    prop:type str,,(RAW,ISCSI)
    prop:gid int,,ID of the grid @index
    prop:iotune dict(int),, Limit disk io
    prop:accountId int,,ID of the account @index
    prop:acl dict(ACE),,access control list
    prop:role str,,role of disk (BOOT; DATA; TEMP) @index
    prop:order int,,order of the disk (as will be shown in OS)
    prop:iqn str,,location of iscsi backend e.g. iqn.2009-11.com.aserver:b6d2aa75-d5ae-4e5a-a38a-12c64c787be6
    prop:diskPath str,, Holds the path of the disk
    prop:login str,,login of e.g. iqn connection
    prop:passwd str,,passwd of e.g. iqn connection
    prop:params str,,pylabs tags to define optional params
    prop:bootPartition int,,the partition to boot from if disk is a bootdisk
    prop:images list(int),,List of id of Image object
    prop:deletionTime int,, epoch time of deletion, in seconds @index

[rootmodel:Network] @dbtype:osis
    """
    """
    prop:id int,,
    prop:name str,,name as given by customer
    prop:descr str,,
    prop:stackId int,,IAAS stack ID
    prop:vlanId str,,ethernet vlan tag
    prop:subnet str,,subnet of the network
    prop:netmask str,,netmask of the network
    prop:nameservers list(str),,Nameservers
    prop:cloudspaceId int,,id of space which holds this network

[model:Nic] @dbtype:osis
    """
    """
    prop:referenceId str,,name as used in hypervisor
    prop:networkId int,,id of Network object
    prop:status str,,status of the vm (ACTIVE;INIT;DOWN)
    prop:deviceName str,,name of the device as on device
    prop:macAddress str,,MAC address of the vnic
    prop:ipAddress str,,IP address of the vnic
    prop:type str,,type of interface (if PUBLIC, then the interface is used to attach vm into public network of the cpu node)
    prop:params str,,pylabs tags to define optional params

[rootmodel:CloudSpace] @dbtype:osis
    """
    """
    prop:id int,,
    prop:name str,,name as given by customer @index
    prop:descr str,,
    prop:acl list(ACE),,access control list @index
    prop:accountId int,, Id of account this cloudspace belongs to @index
    prop:resourceLimits dict(int),,key:$stackid_$cloudunittype value:int amount of max nr of units which can be used there
    prop:networkId int,, Id of the used network @index
    prop:resourceProviderStacks list(int),,Not used anymore here for backwardscompatibility
    prop:externalnetworkip str,, externalnetwork ip linked to the cloudspace @index
    prop:externalnetworkId int,, externalnetwork poold id @index
    prop:allowedVMSizes list(int),, list of allowed sizes
    prop:status str,, status of the cloudspace, e.g VIRTUAL/DEPLOYED/DESTROYED @index
    prop:location str,, datacenterlocation
    prop:gid int,, Grid ID @index
    prop:type str,,Type of gateway to deploy gw or routeros
    prop:secret str,, used to identify a space through the cloud robot
    prop:creationTime int,, epoch time of creation, in seconds @index
    prop:updateTime int,, epoch time of creation, in seconds @index
    prop:deletionTime int,, epoch time of deletion, in seconds @index
    prop:privatenetwork str,,Private network cidr eg. 192.168.103.0/24

[rootmodel:externalnetwork] @dbtype:osis
    """
    externalnetwork pool
    """
    prop:id int,,incremental id of network pool
    prop:gid int,, Grid id @index
    prop:network str,,Network of the pool @index
    prop:subnetmask str,,Subnetmask of the pool @index
    prop:gateway str,,Gateway of th
    prop:vlan int,,VLAN Tag of the network
    prop:name str,,Name of public network
    prop:accountId int,,Account which can use this network @index
    prop:ips list(str),,list of ips
    prop:pingips list(str),, list of ips to be pinged to check for network

[rootmodel:Size] @dbtype:osis
    """
    Size is a combination of memory and cores
    It will map to a specific size on a cloud platform(if this is supported by the platform)
    When not supported, the integration code for the platform uses the disksize and CU.
    """
    prop:id int, 0,id of the size
    prop:name str,,Public name of the size
    prop:memory int,, Memory in Mb @index
    prop:vcpus int,, Number of vcpus assigned to the machine @index
    prop:description str,,Description of the size
	prop:gids list(int),,Grid IDS @index
	prop:disks list(int),, DISK SIZES

[rootmodel:S3user]
    """
    A user on S3
    """
    prop:id int,, id of the S3 user
    prop:name str,, the uid of the S3 user
    prop:cloudspaceId int,, the cloudspace this S3 is assigned to
    prop:s3url str,, the url of the S3 api for this region
    prop:location str,, the region of the S3 api for this user
    prop:accesskey str,, the accesskey to access the S3 interface
    prop:secretkey str,, the secretkey to access the S3 interface

[rootmodel:vmexport]
    """
    A export of a vm. Contains one or multiple files.
    """
    prop:id int,, id of the export
    prop:machineId int,, id of the vmachine
    prop:name str,, name of the export
    prop:type str,, type e.g Raw, condensed, ...
    prop:bucket str,, name of the bucket
    prop:server str,, hostname of the server(for rados None)
    prop:storagetype str,, type of the storage(e.g S3 or RADOS)
    prop:size int,, size of the machine in Mb
    prop:original_size int,, original size of the machine in GB
    prop:timestamp int,, epochtime of the machine
    prop:config str,,json representation machine model
    prop:status str,,status of the vm
    prop:location str,, original machine location
    prop:files str,,json representation of backup content

[rootmodel:resetpasswordtoken]
    """
    A token emailed to a user to reset his/her password
    """
    prop:id str,, The actual reset password token
    prop:username str,, User this token is for @index
    prop:creationTime int,, epoch time of creation, in seconds
    prop:userguid str,, Actual id of the user this token is for @index

[rootmodel:Location] @dbtype:osis
    """
    """
    prop:id int,,id of location
    prop:gid int,, Grid id @index
    prop:name str,,Name of location @index
    prop:locationCode str,,Internal code for location @index
    prop:flag str,,Flag to use for this location

[rootmodel:inviteusertoken]
    """
    A token emailed to a user for sharing machine, cloudspace, accounts management
    """
    prop:id str,, the generated invite token
    prop:email str,, Email of the user that has been invited @index
    prop:lastInvitationTime int,,epoch time of last invitation sent, in seconds (can be later used if we want tokens to expire)
