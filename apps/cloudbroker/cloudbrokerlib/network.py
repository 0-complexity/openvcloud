import netaddr

class Network(object):
    def __init__(self, models):
        self.models = models

    def getPublicIpAddress(self, gid):
        for pool in self.models.publicipv4pool.search({'gid': gid})[1:]:
            if pool['pubips']:
                pool = self.models.publicipv4pool.get(pool['id'])
                pubip = pool.pubips.pop(0)
                self.models.publicipv4pool.set(pool)
                net = netaddr.IPNetwork(pool.id)
                return pool, netaddr.IPNetwork("%s/%s" % (pubip, net.prefixlen))

    def releasePublicIpAddress(self, publicip):
        net = netaddr.IPNetwork(publicip)
        try:
            pool = self.models.publicipv4pool.get(str(net.cidr))
        except:
            pool = None
        if not pool:
            return
        pubips = set(pool.pubips)
        pubips.add(str(net.ip))
        pool.pubips = list(pubips)
        self.models.publicipv4pool.set(pool)
