import netaddr
from cloudbrokerlib import resourcestatus


class Network(object):
    def __init__(self, models):
        self.models = models

    def getExternalIpAddress(self, gid, accountId, externalnetworkId=None):
        query = {"gid": gid, "accountId": {"$in": [accountId, 0]}}
        if externalnetworkId is not None:
            query["id"] = externalnetworkId
        for pool in self.models.externalnetwork.search(query)[1:]:
            for ip in pool["ips"]:
                res = self.models.externalnetwork.updateSearch(
                    {"id": pool["id"]}, {"$pull": {"ips": ip}}
                )
                if res["nModified"] == 1:
                    pool = self.models.externalnetwork.get(pool["id"])
                    return pool, netaddr.IPNetwork("%s/%s" % (ip, pool.subnetmask))

    def releaseExternalIpAddress(self, externalnetworkId, ip):
        net = netaddr.IPNetwork(ip)
        self.models.externalnetwork.updateSearch(
            {"id": externalnetworkId}, {"$addToSet": {"ips": str(net.ip)}}
        )

    def getFreeIPAddress(self, cloudspace):
        query = {
            "cloudspaceId": cloudspace.id,
            "status": {"$nin": resourcestatus.Machine.INVALID_STATES},
        }
        q = {
            "$query": query,
            "$fields": ["nics.ipAddress", "nics.type", "nics.networkId"],
        }
        machines = self.models.vmachine.search(q, size=0)[1:]
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
