from JumpScale import j
from JumpScale.portal.portal.auth import auth as audit
from JumpScale.portal.portal import exceptions
from cloudbrokerlib import authenticator
from cloudbrokerlib.baseactor import BaseActor
from JumpScale.portal.portal import exceptions
import netaddr


class cloudapi_portforwarding(BaseActor):

    """
    Portforwarding api
    uses actor /opt/code/jumpscale/unstable__jumpscale_grid/apps/vfw/actor/jumpscale__netmgr/

    """

    def __init__(self):
        super(cloudapi_portforwarding, self).__init__()
        self.netmgr = j.apps.jumpscale.netmgr

    def _getLocalIp(self, machine):
        for nic in  machine['interfaces']:
            if nic.ipAddress != 'Undefined':
                return nic.ipAddress
        return None

    @authenticator.auth(acl={'cloudspace': set('C')})
    @audit()
    def create(self, cloudspaceId, publicIp, publicPort, machineId, localPort, protocol=None, **kwargs):
        """
        Create a port forwarding rule

        :param cloudspaceId: id of the cloudspace
        :param publicIp: public ipaddress
        :param publicPort: public port
        :param machineId: id of the virtual machine
        :param localPort: local port on vm
        :param protocol: protocol udp or tcp
        """
        machineId = int(machineId)
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if publicPort > 65535 or publicPort < 1:
            raise exceptions.BadRequest("Public port should be between 1 and 65535")
        if localPort > 65535 or localPort < 1:
            raise exceptions.BadRequest("Local port should be between 1 and 65535")
        if protocol and protocol not in ('tcp', 'udp'):
            raise exceptions.BadRequest("Protocol should be either tcp or udp")

        if len(fw) == 0:
            raise exceptions.NotFound('Incorrect cloudspace or there is no corresponding gateway')
        fw_id = fw[0]['guid']
        grid_id = fw[0]['gid']

        try:
            publicIp = str(netaddr.IPNetwork(publicIp).ip)
        except netaddr.AddrFormatError:
            raise exceptions.BadRequest("Invalid public IP %s" % publicIp)

        machine = j.apps.cloudapi.machines.get(machineId)
        localIp = self._getLocalIp(machine)
        if localIp is None:
            raise exceptions.NotFound('No correct ipaddress found for this machine')

        if self._selfcheckduplicate(fw_id, publicIp, publicPort, protocol, cloudspace.gid):
            raise exceptions.Conflict("Forward to %s with port %s already exists" % (publicIp, publicPort))
        try:
            result = self.netmgr.fw_forward_create(fw_id, grid_id, publicIp, publicPort, localIp, localPort, protocol)
        except:
            raise exceptions.ServiceUnavailable("Forward to %s with port %s failed to create." % (publicIp, publicPort))
        return result

    def deleteByVM(self, machine, **kwargs):
        def getIP():
            for nic in machine.nics:
                if nic.ipAddress != 'Undefined':
                    return nic.ipAddress
            return None
        localIp = getIP()
        if localIp is None:
            return True
        cloudspaceId = machine.cloudspaceId
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if not fw:
            return True
        fw_id = fw[0]['guid']
        grid_id = fw[0]['gid']
        forwards = self.netmgr.fw_forward_list(fw_id, grid_id)
        for fw in forwards:
            if fw['localIp'] == localIp:
                self._deleteByPort(cloudspaceId, fw['publicIp'], fw['publicPort'], fw['protocol'])
        return True

    def _selfcheckduplicate(self, fw_id, publicIp, publicPort, protocol, gid):
        forwards = self.netmgr.fw_forward_list(fw_id, gid)
        for fw in forwards:
            if fw['publicIp'] == publicIp \
               and int(fw['publicPort']) == publicPort \
               and fw['protocol'] == protocol:
                return True
        return False

    def _getFirewallId(self, cloudspaceId):
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if len(fw) == 0:
            raise exceptions.NotFound('Incorrect cloudspace or there is no corresponding gateway')

        return fw[0]['guid'], fw[0]['gid']

    @authenticator.auth(acl={'cloudspace': set('X')})
    @audit()
    def delete(self, cloudspaceId, id, **kwargs):
        """
        Delete a specific port forwarding rule

        :param cloudspaceId: id of the cloudspace
        :param id: id of the port forward rule

        """
        try:
            result = self._delete(int(cloudspaceId), id)
        except exceptions.BaseError:
            raise
        except:
            raise exceptions.ServiceUnavailable('Failed to remove Portforwarding')
        return result

    def _delete(self, cloudspaceId, id, **kwargs):
        fw_id, fw_gid = self._getFirewallId(cloudspaceId)
        forwards = self.netmgr.fw_forward_list(fw_id, fw_gid)
        id = int(id)
        if not id < len(forwards):
            raise exceptions.NotFound('Cannot find the rule with id %s' % str(id))
        forward = forwards[id]
        self.netmgr.fw_forward_delete(fw_id, fw_gid, forward['publicIp'], forward['publicPort'],
                                      forward['localIp'], forward['localPort'])
        forwards = self.netmgr.fw_forward_list(fw_id, fw_gid)
        return self._process_list(forwards, cloudspaceId)

    @authenticator.auth(acl={'cloudspace': set('X')})
    @audit()
    def deleteByPort(self, cloudspaceId, publicIp, publicPort, proto=None, **kwargs):
        """
        Delete a specific port forwarding rule by public port details

        :param cloudspaceId: id of the cloudspace
        :param publicIp: port forwarding public ip
        :param publicPort: port forwarding public port
        :param proto: port forwarding protocol
        """
        try:
            result = self._deleteByPort(int(cloudspaceId), publicIp, publicPort, proto)
        except exceptions.BaseError:
            raise
        except:
            raise exceptions.ServiceUnavailable('Failed to remove Portforwarding')
        return True

    def _deleteByPort(self, cloudspaceId, publicIp, publicPort, proto, **kwargs):
        fw_id, fw_gid = self._getFirewallId(cloudspaceId)
        if not self.netmgr.fw_forward_delete(fw_id, fw_gid, publicIp, publicPort,proto):
            raise exceptions.NotFound("Could not find port forwarding with %s:%s %s" % (publicIp, publicPort, proto))
        forwards = self.netmgr.fw_forward_list(fw_id, fw_gid)
        return self._process_list(forwards, cloudspaceId)

    @authenticator.auth(acl={'cloudspace': set('C')})
    @audit()
    def update(self, cloudspaceId, id, publicIp, publicPort, machineId, localPort, protocol, **kwargs):
        """
        Update a port forwarding rule

        :param cloudspaceId: id of the cloudspace
        :param id: id of the portforward to edit
        :param publicIp: public ipaddress
        :param publicPort: public port
        :param machineId: id of the virtual machine
        :param localPort: local port
        :param protocol: protocol udp or tcp
        """
        machineId = int(machineId)
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if len(fw) == 0:
            raise exceptions.NotFound('Incorrect cloudspace or there is no corresponding gateway')
        fw_id = fw[0]['guid']

        forwards = self.netmgr.fw_forward_list(fw_id, cloudspace.gid)
        id = int(id)
        if not id < len(forwards):
            raise exceptions.NotFound('Cannot find the rule with id %s' % str(id))
        forward = forwards[id]
        machine = self.models.vmachine.get(machineId)
        if machine.nics:
            if machine.nics[0].ipAddress != 'Undefined':
                localIp = machine.nics[0].ipAddress
            else:
                raise exceptions.NotFound('No correct ipaddress found for machine with id %s' % machineId)
        self.netmgr.fw_forward_delete(fw_id, cloudspace.gid,
                                      forward['publicIp'], forward['publicPort'], forward['localIp'], forward['localPort'], forward['protocol'])
        if self._selfcheckduplicate(fw_id, publicIp, publicPort, protocol, cloudspace.gid):
            raise exceptions.Conflict("Forward for %s with port %s already exists" % (publicIp, publicPort))
        self.netmgr.fw_forward_create(fw_id, cloudspace.gid, publicIp, publicPort, localIp, localPort, protocol)
        forwards = self.netmgr.fw_forward_list(fw_id, cloudspace.gid)
        return self._process_list(forwards, cloudspaceId)

    def _process_list(self, forwards, cloudspaceId):
        result = list()
        query = {'cloudspaceId': cloudspaceId, 'status': {'$ne': 'DESTROYED'}}
        machines = self.models.vmachine.search(query)[1:]
        def getMachineByIP(ip):
            for machine in machines:
                for nic in machine['nics']:
                    if nic['ipAddress'] == ip:
                        return machine

        for index, f in enumerate(forwards):
            f['id'] = index
            machine = getMachineByIP(f['localIp'])
            if machine is None:
                f['vmName'] = f['localIp']
            else:
                f['vmName'] = "%s (%s)" % (machine['name'], f['localIp'])
                f['vmid'] = machine['id']
            if not f['protocol']:
                f['protocol'] = 'tcp'
            result.append(f)
        return result

    @authenticator.auth(acl={'cloudspace': set('R'), 'machine': set('R')})
    @audit()
    def list(self, cloudspaceId, machineId=None, **kwargs):
        """
        List all port forwarding rules in a cloudspace or machine

        :param cloudspaceId: id of the cloudspace
        :param machineId: id of the machine, all rules of cloudspace will be listed if set to None
        """
        machine = None
        if machineId:
            machineId = int(machineId)
            machine = self.models.vmachine.get(machineId)
        def getIP():
            if machine:
                for nic in machine.nics:
                    if nic.ipAddress != 'Undefined':
                        return nic.ipAddress
            return None
        localip = getIP()
        cloudspaceId = int(cloudspaceId)
        cloudspace = self.models.cloudspace.get(cloudspaceId)
        fw = self.netmgr.fw_list(cloudspace.gid, cloudspaceId)
        if len(fw) == 0:
            raise exceptions.NotFound('Incorrect cloudspace or there is no corresponding gateway')
        fw_id = fw[0]['guid']
        fw_gid = fw[0]['gid']
        forwards = self.netmgr.fw_forward_list(fw_id, fw_gid, localip)
        return self._process_list(forwards, cloudspaceId)

    @audit()
    def listcommonports(self, **kwargs):
        """
        List a range of predifined ports
        """
        return [{'name': 'http', 'port': 80, 'protocol': 'tcp'},
                {'name': 'ftp', 'port': 21, 'protocol': 'tcp'},
                {'name': 'ssh', 'port': 22, 'protocol': 'tcp'}]
