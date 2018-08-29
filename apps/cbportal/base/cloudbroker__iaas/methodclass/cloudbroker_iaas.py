from JumpScale import j
from JumpScale.portal.portal import exceptions
import netaddr
import socket
from cloudbrokerlib.authenticator import auth
from cloudbrokerlib.baseactor import BaseActor

json = j.db.serializers.ujson


def checkIPS(network, ips):
    for ip in ips:
        if netaddr.IPAddress(ip) not in network:
            return False
    return True


class cloudbroker_iaas(BaseActor):
    """
    gateway to grid
    """

    def __init__(self):
        super(cloudbroker_iaas, self).__init__()
        self.lcl = j.clients.osis.getNamespace("libvirt")

    def _checkPingIps(self, pingips):
        pingips = pingips.split(",")
        res = []
        for pingip in pingips:
            pingip = pingip.lstrip()
            try:
                socket.inet_aton(pingip)
            except socket.error:
                raise exceptions.BadRequest(
                    "Illegal ip address passed in pingips: %s" % pingip
                )
            res.append(pingip)
        return res

    @auth(groups=["level1", "level2", "level3"])
    def addExternalNetwork(
        self,
        name,
        subnet,
        gateway,
        startip,
        endip,
        gid,
        vlan,
        accountId,
        pingips,
        **kwargs
    ):
        """
        Adds a public network range to be used for cloudspaces
        param:subnet the subnet to add in CIDR notation (x.x.x.x/y)
        """
        gateway = gateway.strip()
        try:
            net = netaddr.IPNetwork(subnet)
            if netaddr.IPAddress(startip) not in net:
                raise exceptions.BadRequest(
                    "Start IP Addresses %s is not in subnet %s" % (startip, subnet)
                )
            if netaddr.IPAddress(endip) not in net:
                raise exceptions.BadRequest(
                    "End IP Addresses %s is not in subnet %s" % (endip, subnet)
                )
            if not checkIPS(net, [gateway]):
                raise exceptions.BadRequest(
                    "Gateway Address %s is not in subnet %s" % (gateway, subnet)
                )
            if self.models.externalnetwork.count({"vlan": vlan}) > 0:
                raise exceptions.Conflict(
                    "VLAN {} is already in use by another external network"
                )
        except netaddr.AddrFormatError as e:
            raise exceptions.BadRequest(e.message)

        if pingips is None:
            pingips = "8.8.8.8"
        pingips = self._checkPingIps(pingips)

        pool = self.models.externalnetwork.new()
        pool.gid = int(gid)
        pool.gateway = gateway
        pool.name = name
        pool.pingips = pingips
        pool.vlan = vlan or 0
        pool.subnetmask = str(net.netmask)
        pool.network = str(net.network)
        pool.accountId = accountId or 0
        pool.ips = [str(ip) for ip in netaddr.IPRange(startip, endip)]
        pool.id, _, _ = self.models.externalnetwork.set(pool)
        return pool.id

    @auth(groups=["level1", "level2", "level3"])
    def getUsedIPInfo(self, pool):
        network = {"spaces": [], "vms": []}
        for space in self.models.cloudspace.search(
            {
                "$query": {
                    "gid": pool.gid,
                    "externalnetworkId": pool.id,
                    "status": "DEPLOYED",
                },
                "$fields": ["id", "name", "externalnetworkip"],
            }
        )[1:]:
            network["spaces"].append(space)
        for vm in self.models.vmachine.search(
            {"nics.type": "PUBLIC", "status": {"$nin": ["ERROR", "DESTROYED"]}}
        )[1:]:
            for nic in vm["nics"]:
                if nic["type"] == "PUBLIC":
                    tagObject = j.core.tags.getObject(nic["params"])
                    if int(tagObject.tags.get("externalnetworkId", 0)) == pool.id:
                        vm["externalnetworkip"] = nic["ipAddress"]
                        network["vms"].append(vm)
        return network

    def _getUsedIPS(self, pool):
        networkinfo = self.getUsedIPInfo(pool)
        usedips = set()
        for obj in networkinfo["vms"] + networkinfo["spaces"]:
            ip = str(netaddr.IPNetwork(obj["externalnetworkip"]).ip)
            usedips.add(ip)
        return usedips

    @auth(groups=["level1", "level2", "level3"])
    def deleteExternalNetwork(self, externalnetworkId, **kwargs):
        if not self.models.externalnetwork.exists(externalnetworkId):
            raise exceptions.NotFound(
                "Could not find external network with id %s" % externalnetworkId
            )
        cloudCount = self.models.cloudspace.count(
            {"externalnetworkId": externalnetworkId, "status": {"$ne": "DESTROYED"}}
        )
        machineCount = self.models.vmachine.count(
            {
                "nics.params": {"$regex": "externalnetworkId:{}($|\D)".format(externalnetworkId)}, 
                "status": {"$ne": "DESTROYED"}
            }
        )
        if cloudCount == 0 and machineCount == 0:
            self.models.externalnetwork.delete(externalnetworkId)
        else:
            raise exceptions.Conflict("Cannot delete, external network in use")
        return True

    @auth(groups=["level1", "level2", "level3"])
    def addExternalIPS(self, externalnetworkId, startip, endip, **kwargs):
        """
        Add public ips to an existing range
        """
        if not self.models.externalnetwork.exists(externalnetworkId):
            raise exceptions.NotFound(
                "Could not find external network with id %s" % externalnetworkId
            )
        pool = self.models.externalnetwork.get(externalnetworkId)
        try:
            net = netaddr.IPNetwork("{}/{}".format(pool.network, pool.subnetmask))
            if netaddr.IPAddress(startip) not in net:
                raise exceptions.BadRequest(
                    "Start IP Addresses %s is not in subnet %s" % (startip, net)
                )
            if netaddr.IPAddress(endip) not in net:
                raise exceptions.BadRequest(
                    "End IP Addresses %s is not in subnet %s" % (endip, net)
                )
        except netaddr.AddrFormatError as e:
            raise exceptions.BadRequest(e.message)
        ips = set(pool.ips)
        newset = {str(ip) for ip in netaddr.IPRange(startip, endip)}
        usedips = self._getUsedIPS(pool)
        duplicateips = usedips.intersection(newset)
        if duplicateips:
            raise exceptions.Conflict(
                "New range overlaps with existing deployed IP Addresses"
            )
        ips.update(newset)
        pool.ips = list(ips)
        self.models.externalnetwork.set(pool)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def changeIPv4Gateway(self, externalnetworkId, gateway, **kwargs):
        gateway = gateway.strip()
        if not self.models.externalnetwork.exists(externalnetworkId):
            raise exceptions.NotFound(
                "Could not find externalnetwork with id %s" % externalnetworkId
            )

        pool = self.models.externalnetwork.get(externalnetworkId)
        try:
            net = netaddr.IPNetwork("{}/{}".format(pool.network, pool.subnetmask))
            if not checkIPS(net, [gateway]):
                raise exceptions.BadRequest(
                    "Gateway Address %s is not in subnet %s" % (gateway, net)
                )
        except netaddr.AddrFormatError as e:
            raise exceptions.BadRequest(e.message)

        pool.gateway = gateway
        self.models.externalnetwork.set(pool)

    @auth(groups=["level1", "level2", "level3"])
    def removeExternalIPs(self, externalnetworkId, freeips, **kwargs):
        """
        Remove public ips from an existing range
        """
        ctx = kwargs["ctx"]
        if not self.models.externalnetworkId.exists(externalnetworkId):
            ctx.start_response("404 Not Found")
            return "Could not find externalnetwork with subnet %s" % externalnetworkId
        pool = self.models.externalnetwork.get(externalnetworkId)
        net = netaddr.IPNetwork("{}/{}".format(pool.network, pool.subnetmask))
        if not checkIPS(net, freeips):
            ctx.start_response("400 Bad Request")
            return "One or more IP Addresses %s is not in subnet %s" % (net)
        pool.pubips = list(set(pool.pubips) - set(freeips))
        self.models.externalnetwork.set(pool)
        return True

    @auth(groups=["level1", "level2", "level3"])
    def removeExternalIP(self, externalnetworkId, ip, **kwargs):
        """
        Remove External IP Addresses
        """
        if not self.models.externalnetwork.exists(externalnetworkId):
            raise exceptions.NotFound(
                "Could not find externalnetwork with id %s" % externalnetworkId
            )
        self.models.externalnetwork.updateSearch(
            {"id": externalnetworkId}, {"$pull": {"ips": ip}}
        )
        return True

    @auth(groups=["level1", "level2", "level3"])
    def editPingIps(self, externalnetworkId, pingips, **kwargs):
        """
        Edit list of ips pinged for network check
        """
        if not self.models.externalnetwork.exists(externalnetworkId):
            raise exceptions.NotFound(
                "Could not find externalnetwork with id %s" % externalnetworkId
            )
        pingips = self._checkPingIps(pingips)
        self.models.externalnetwork.updateSearch(
            {"id": externalnetworkId}, {"$set": {"pingips": pingips}}
        )
        return True

    @auth(groups=["level1", "level2", "level3"])
    def addSize(self, name, vcpus, memory, disksize, **kwargs):
        """
        Add a new size to grid location.

        @param name: str name of new size.
        @param vcpus: int  number of vcpus to be used.
        @param memory: int  amount of memory for this size.
        @param disksize: [int] list of disk sizes available.
        """
        size = dict()
        disks = map(int, disksize.split(","))
        size["disks"] = disks
        size["memory"] = memory
        size["vcpus"] = vcpus
        locations = self.models.location.search({"$query": {}, "$fields": ["gid"]})
        size["gids"] = [location["gid"] for location in locations[1:]]
        size["name"] = name
        cloudbroker_size = next(
            iter(self.models.size.search({"vcpus": vcpus, "memory": memory})[1:]), None
        )

        if not cloudbroker_size:
            self.models.size.set(size)
        else:
            update = {"$addToSet": {"disks": {"$each": disks}}}
            self.models.size.updateSearch({"id": cloudbroker_size["id"]}, update)
            self.models.size.set(cloudbroker_size)

        return True

    @auth(groups=["level1", "level2", "level3"])
    def deleteSize(self, size_id, **kwargs):
        """
        Delete unused size in location.

        @param size_id: int id if size to be deleted.
        """
        if self.models.vmachine.count({"sizeId": size_id}) == 0:
            self.models.size.delete(size_id)
        return True
