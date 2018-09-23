[actor] @dbtype:mem,fs
    """
    Operator actions on nodes
    """
    method:maintenance
        """
        Place node in maintenance state
        """
        var:nid int,,nid of node
        var:vmaction str,, what to do with running vms move or stop @optional

    method:enable
        """
        Enable node from maintenance status to enabled 
        """
        var:nid int,,nid of node
        var:message str,,message. Must be less than 30 characters @optional

    method:enableNodes
        """
        Enable node from maintenance status to enabled 
        """
        var:nids list(int),,nids of storagerouter
        var:message str,,message. Must be less than 30 characters @optional

    method:decommission
        """
        Set node status to 'DECOMMISSIONED' and remove from relevant process for vms and markoff for storage routers
        """
        var:nid int,,nid of node
        var:vmaction str,, what to do with running vms move or stop @optional

    method:applyIpmiAction
        """
        apply ipmi action on node
        """
        var:nid int,,nid of node
        var:action str,, on of actions power_on shutdown force_shutdown reboot
