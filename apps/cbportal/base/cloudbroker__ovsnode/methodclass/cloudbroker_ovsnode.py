import time
from JumpScale import j
from JumpScale.portal.portal import exceptions
from cloudbrokerlib.baseactor import BaseActor


class cloudbroker_ovsnode(BaseActor):
    def __init__(self):
        super(cloudbroker_ovsnode, self).__init__()
        self.node = j.apps.cloudbroker.node

    def activateNodes(self, nids, **kwargs):
        for nid in nids:
            node = self.node._getNode(nid)
            self.node.scheduleJumpscripts(
                nid, node["gid"], category="monitor.healthcheck"
            )
        return self.sysmodels.node.updateSearch(
            {"id": {"$in": nids}}, {"$set": {"status": "ENABLED"}}
        )

    def getStorageIP(self, nid, **kwargs):
        """
        get the storage ip from the models
        """
        node = self.node._getNode(nid)
        for netaddr in node["netaddr"]:
            if netaddr["name"] == "storage":
                return netaddr["ip"][0]
        else:
            raise exceptions.BadRequest(
                "Storage Node does not have interface for storage ip , please specify storage interface"
            )

    def deactivateNodes(self, nids, **kwargs):
        if len(nids) != 1:
            raise exceptions.BadRequest("Can only deactivate 1 Storagerouter at a time")
        nid = nids[0]
        ctx = kwargs["ctx"]
        node = self.node._getNode(nid)
        edgeinfo = None
        myips = []
        for nic in node["netaddr"]:
            myips.extend(nic["ip"])

        if "storagedriver" not in node["roles"]:
            raise exceptions.BadRequest("Node with nid %s is not a storagedriver" % nid)

        driver = self.cb.getProviderByGID(node["gid"])
        alledgeclients = driver.all_edgeclients[:]
        for edgeclient in alledgeclients:
            if edgeclient["storageip"] in myips:
                edgeinfo = edgeclient
                continue

        if edgeinfo is None:
            raise exceptions.Error("Could not find storage IP on node %s" % nid)

        edgeclients = filter(
            lambda c: c["storageip"] != edgeclient["storageip"], alledgeclients
        )
        if not edgeclients:
            raise exceptions.BadRequest("No storage routers available to migrate to")
        self.sysmodels.node.updateSearch({"id": nid}, {"$set": {"status": "MAINTENANCE"}})

        def get_vpool_name(host, port):
            for edgeclient in alledgeclients:
                if edgeclient["storageip"] == host and edgeclient["edgeport"] == port:
                    return edgeclient["vpool"]
            return None

        diskguids = driver.list_vdisks(edgeinfo["storagerouterguid"])
        while diskguids:
            hasworked = False
            for idx, diskguid in enumerate(diskguids):
                ctx.events.sendMessage(
                    "Deactivate Storagerouter",
                    "Moving Storagerouter on vDisk %s/%s" % (idx + 1, len(diskguids)),
                )
                disk = self.models.disk.searchOne({"referenceId": {"$regex": diskguid}})
                if not disk:
                    continue
                hasworked = True
                volume = j.apps.cloudapi.disks.getStorageVolume(disk, driver)
                vpool = get_vpool_name(volume.edgehost, volume.edgeport)
                client = driver.getNextEdgeClient(vpool, edgeclients)
                client["vdiskcount"] += 1
                oldloc = "{}:{}".format(volume.edgehost, volume.edgeport)
                newloc = "{}:{}".format(client["storageip"], client["edgeport"])
                disk["referenceId"] = disk["referenceId"].replace(oldloc, newloc)
                self.models.disk.set(disk)
                kwargs = {
                    "storagerouterguid": client["storagerouterguid"],
                    "ovs_connection": driver.ovs_connection,
                    "diskguid": volume.vdiskguid,
                }
                driver._execute_agent_job("move_disk", role="storagemaster", **kwargs)
            if not hasworked:
                break
            diskguids = driver.list_vdisks(edgeinfo["storagerouterguid"])

        gid = node["gid"]
        self.cb.executeJumpscript("cloudscalers", "nodestatus", nid=nid, gid=gid)
        self.node.unscheduleJumpscripts(nid, gid, category="monitor.healthcheck")
        time.sleep(5)
        self.sysmodels.health.deleteSearch({"nid": nid})

        ctx.events.sendMessage(
            "Deactivate Storagerouter", "Finished moving all vdisks", "success"
        )
        return "Finished Deactivating Storagerouter"
