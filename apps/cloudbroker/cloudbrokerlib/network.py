import netaddr
from cloudbrokerlib import resourcestatus


class Network(object):
    def __init__(self, db):
        self.db = db

    def getExternalIpAddress(self, gid, accountId, externalnetworkId=None):
        query = {"gid": gid, "accountId": {"$in": [accountId, 0]}}
        if externalnetworkId is not None:
            query["id"] = externalnetworkId
        for pool in self.db.cloudbroker.externalnetwork.search(query)[1:]:
            for ip in pool["ips"]:
                res = self.models.externalnetwork.updateSearch(
                    {"id": pool["id"]}, {"$pull": {"ips": ip}}
                )
                if res["nModified"] == 1:
                    pool = self.db.cloudbroker.externalnetwork.get(pool["id"])
                    return pool, netaddr.IPNetwork("%s/%s" % (ip, pool.subnetmask))

    def releaseExternalIpAddress(self, externalnetworkId, ip):
        net = netaddr.IPNetwork(ip)
        self.db.cloudbroker.externalnetwork.updateSearch(
            {"id": externalnetworkId}, {"$addToSet": {"ips": str(net.ip)}}
        )

    def getFreeMacAddress(self, gid, **kwargs):
        """
        Get a free macaddres in this libvirt environment
        result
        """
        mac = self.db.libvirt.macaddress.set(key=gid, obj=1)
        firstmac = netaddr.EUI("52:54:00:00:00:00")
        newmac = int(firstmac) + mac
        macaddr = netaddr.EUI(newmac)
        macaddr.dialect = netaddr.mac_eui48
        return str(macaddr).replace("-", ":").lower()

    def getFreeIPAddress(self, cloudspace):
        query = {
            "cloudspaceId": cloudspace.id,
            "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
        }
        q = {
            "$query": query,
            "$fields": ["nics.ipAddress", "nics.type", "nics.networkId"],
        }
        machines = self.db.cloudbroker.vmachine.search(q, size=0)[1:]
        network = netaddr.IPNetwork(cloudspace.privatenetwork)
        usedips = [
            netaddr.IPAddress(nic["ipAddress"])
            for vm in machines
            for nic in vm["nics"]
            if nic["type"] == "bridge" and nic["ipAddress"] != "Undefined"
        ]
        usedips.append(network.ip)
        ip = network.broadcast - 1
        while ip in network:
            if ip not in usedips:
                return str(ip)
            else:
                ip -= 1
        else:
            raise RuntimeError("No more free IP addresses for space")
