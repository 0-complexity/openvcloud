[actor] @dbtype:mem,fs
    """
    Operator actions for handling interventions on a a grid
    """

    method:purgeLogs
        """
        Remove logs & eco's
        By default the logs en eco's older than than 1 week but this can be overriden
        """
        var:gid int,, id of the grid
        var:age str,, by default 1 week (-1h, -1w TODO: check the options in the jsgrid purgelogs)
        result: bool

    method:checkVMs
        """
        Run checkvms jumpscript
        """
        var:gid int,, id of the grid
        result: bool

    method:rename
        """
        Rename a grid/location
        """
        var:gid int,, id of the grid
        var:name str,, New name of the location @validator:name
        result: bool

    method:add
        """
        Adds a location/grid
        """
        var:gid int,, id of the grid
        var:name str,, Name of the location @validator:name
        var:locationcode str,, Location code typicly used in dns names
        result: str

    method:upgrade
        """
        upgrade the grid to the latest
        """
        var:url str,, Version to update to
    
    method:runUpgradeScript
        """
        Run version migration scripts
        """
        result: str

    method:upgradeFailed
        """
        Set status of current installing version to Error
        """
        result: str

    method:changeSettings
        """
        changes grid settings
        """
        var:id int,, id of the grid
        var:settings str,, json data of the new settings will override old data
        result: str

    method:executeMaintenanceScript
        """
        Executes maintenance script
        """
        var:gid str,, id of the grid
        var:nodestype str,, Type of nodes you want to apply the action on
        var:script str,, the script you want to run

    method:status @method:get,post noauth
        """
        Check if current environment is active
        """

    method:createSystemSpace
        """
        create system space
        """
        var:id int,, id of the grid
        var:name str,, name of the account/cloudspace to be created for the system @tags validator:name
        var:imageId int,, id of the specific image
        var:bootsize int,, size of base volume
        var:dataDiskSize int,, data disk size in gigabytes
        var:sizeId int,,id of the specific size @optional
        var:vcpus int,,number of vcpus to provide @optional
        var:memory int,,amount of memory to provide @optional
        result: str


    method:listVersions
        """
        list versions
        """
        var:status str,, filter by version status @optional

    method:deleteVersion
        """
        Delete version by id
        """
        var:id int,, version id