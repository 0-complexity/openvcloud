from JumpScale import j
from JumpScale.portal.portal import exceptions
import time
import uuid
import netaddr

DEFAULTCIDR = "192.168.103.0/24"


class NetManager(object):
    """
    net manager

    """

    def __init__(self, cb):
        self.client = j.clients.osis.getByInstance("main")
        self.osisvfw = j.clients.osis.getCategory(self.client, "vfw", "virtualfirewall")
        self.nodeclient = j.clients.osis.getCategory(self.client, "system", "node")
        self.cbmodel = j.clients.osis.getNamespace("cloudbroker")
        self.gridclient = j.clients.osis.getCategory(self.client, "system", "grid")
        self.json = j.db.serializers.getSerializerType("j")
        self._ovsdata = {}
        self.cb = cb

    def get_ovs_credentials(self, gid):
        cachekey = "credentials_{}".format(gid)
        if cachekey not in self._ovsdata:
            grid = self.gridclient.get(gid)
            credentials = grid.settings["ovs_credentials"]
            self._ovsdata[cachekey] = credentials
        return self._ovsdata[cachekey]

    def get_ovs_connection(self, gid):
        cachekey = "ovs_connection_{}".format(gid)
        if cachekey not in self._ovsdata:
            ovs_credentials = self.get_ovs_credentials(gid)
            connection = {
                "ips": ovs_credentials["ips"],
                "client_id": ovs_credentials["client_id"],
                "client_secret": ovs_credentials["client_secret"],
            }
            self._ovsdata[cachekey] = connection
        return self._ovsdata[cachekey]

    def _getVFWObject(self, fwid):
        try:
            fwobj = self.osisvfw.get(fwid)
        except:
            raise exceptions.ServiceUnavailable(
                "VFW with id %s is not deployed yet!" % fwid
            )
        if not fwobj.nid:
            raise exceptions.ServiceUnavailable(
                "VFW with id %s is not deployed yet!" % fwid
            )
        return fwobj

    def fw_create(
        self,
        gid,
        domain,
        publicip,
        type,
        networkid,
        publicgwip,
        vlan,
        targetNid=None,
        privatenetwork=DEFAULTCIDR,
        **kwargs
    ):
        """
        param:domain needs to be unique name of a domain,e.g. a group, space, ... (just to find the FW back)
        param:gid grid id
        param:nid node id
        param:masquerade do you want to allow masquerading?
        param:login admin login to the firewall
        param:host management address to manage the firewall
        param:type type of firewall e.g routeros, ...
        """
        vfw = self.osisvfw.new()
        vfw.domain = domain
        vfw.id = networkid
        vfw.gid = gid
        vfw.privatenetwork = privatenetwork
        vfw.external.ips = [publicip]
        vfw.external.vlan = vlan
        vfw.external.gateway = publicgwip
        vfw.type = type
        vfw.state = "STARTED"
        vfw.guid = self.osisvfw.set(vfw)[0]
        return self._fw_create(vfw, targetNid)

    def _fw_create(self, vfw, targetNid, isnew=True):
        args = {"name": "%s_%s" % (vfw.domain, vfw.name)}
        if targetNid:
            nid = targetNid
        else:
            nid = int(
                self.cb.getBestStack(vfw.gid, memory=128, routeros=True)[
                    "referenceId"
                ]
            )
        vfw.nid = nid
        self.osisvfw.set(vfw)
        if vfw.type == "routeros":
            args = {"vfw": vfw.dump()}
            job = self.cb.scheduleCmd(
                nid=nid,
                cmdcategory="jumpscale",
                cmdname="vfs_create_routeros",
                gid=vfw.gid,
                args=args,
                wait=True,
            )
            vfw.deployment_jobguid = job["guid"]
            self.osisvfw.set(vfw)
            result = self.cb.agentcontroller.waitJumpscript(job=job)

            if result["state"] != "OK":
                if isnew:
                    self.osisvfw.delete(vfw.guid)
                raise exceptions.ServiceUnavailable(
                    "Failed to create fw for domain %s job was %s"
                    % (vfw.domain, result["id"])
                )
            data = result["result"]
            vfw.host = data["internalip"]
            vfw.username = data["username"]
            vfw.password = data["password"]
            self.osisvfw.set(vfw)
            self.fw_reapply(vfw.guid)
            return result
        else:
            fwobj = vfw.dump()
            fwobj["leases"], fwobj["cloud-init"] = self.cb.cloudspace.get_leases_cloudinit(
                int(fwobj["domain"])
            )
            args = {"vfw": fwobj}
            job = self.cb.scheduleCmd(
                nid=nid,
                cmdcategory="jumpscale",
                cmdname="vfs_create",
                gid=vfw.gid,
                args=args,
                wait=True,
            )
            vfw.deployment_jobguid = job["guid"]
            self.osisvfw.set(vfw)
            result = self.cb.agentcontroller.waitJumpscript(job=job)
            if result["state"] != "OK":
                if isnew:
                    self.osisvfw.delete(vfw.guid)
                raise exceptions.ServiceUnavailable(
                    "Failed to create fw for domain %s job was %s"
                    % (vfw.domain, result["id"])
                )
            return result

    def fw_move(self, fwid, targetNid, **kwargs):
        fwobj = self._getVFWObject(fwid)
        srcnode = self.nodeclient.get("%s_%s" % (fwobj.gid, fwobj.nid))

        def get_backplane_ip(node):
            for nicinfo in node.netaddr:
                if nicinfo["name"] == "backplane1":
                    return nicinfo["ip"][0]

        srcip = get_backplane_ip(srcnode)
        if fwobj.type == "routeros":
            return self.fw_migrate(fwobj, srcip, targetNid, **kwargs)
        else:
            self.fw_stop(fwobj.guid)
            return self.fw_start(fwobj.guid, resettype="factory", targetNid=targetNid)

    def fw_migrate(self, fwobj, sourceip, targetNid, **kwargs):
        args = {
            "networkid": fwobj.id,
            "vlan": fwobj.external.vlan,
            "externalip": fwobj.external.ips[0],
            "sourceip": sourceip,
        }
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        if fwobj.type != "routeros":
            raise RuntimeError("Can not migrate vfw of type {}".format(fwobj.type))
        job = self.cb.executeJumpscript(
            "jumpscale", "vfs_migrate_routeros", nid=targetNid, gid=fwobj.gid, args=args
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable(
                "Failed to move routeros check job %(guid)s" % job
            )
        if job["result"]:
            args = {"networkid": fwobj.id, "domainxml": job["result"]}
            self.cb.executeJumpscript(
                "greenitglobe",
                "cleanup_network",
                nid=fwobj.nid,
                gid=fwobj.gid,
                args=args,
            )
            self.osisvfw.updateSearch(
                {"guid": fwobj.guid}, {"$set": {"nid": targetNid}}
            )
        return job["result"]

    def fw_executescript(self, fwid, script):
        fwobj = self._getVFWObject(fwid)
        args = {"fwobject": fwobj.obj2dict(), "script": script}
        job = self.cb.executeJumpscript(
            "jumpscale",
            "vfs_runscript_routeros",
            nid=fwobj.nid,
            gid=fwobj.gid,
            args=args,
        )
        if job["state"] != "OK":
            raise exceptions.BadRequest("Failed to execute script")
        result, err = job["result"]
        if err:
            raise exceptions.BadRequest("Failed to execute script: %s" % err)
        self.osisvfw.updateSearch(
            {"guid": fwid}, {"$set": {"accesstime": int(time.time())}}
        )
        return True

    def fw_get_ipaddress(self, fwid, macaddress):
        fwobj = self._getVFWObject(fwid)
        args = {"fwobject": fwobj.obj2dict(), "macaddress": macaddress}
        job = self.cb.executeJumpscript(
            "jumpscale",
            "vfs_get_ipaddress_routeros",
            gid=fwobj.gid,
            nid=fwobj.nid,
            args=args,
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable(
                "Failed to retreive IPAddress for macaddress %s. Error: %s"
                % (macaddress, job["result"]["errormessage"])
            )
        return job["result"]

    def fw_remove_lease(self, fwid, macaddress):
        fwobj = self._getVFWObject(fwid)
        args = {"fwobject": fwobj.obj2dict(), "macaddress": macaddress}
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        job = self.cb.executeJumpscript(
            "jumpscale",
            "vfs_remove_lease_routeros",
            gid=fwobj.gid,
            nid=fwobj.nid,
            args=args,
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable(
                "Failed to release lease for macaddress %s. Error: %s"
                % (macaddress, job["result"]["errormessage"])
            )
        return job["result"]

    def fw_set_password(self, fwid, username, password):
        fwobj = self._getVFWObject(fwid)
        args = {
            "fwobject": fwobj.obj2dict(),
            "username": username,
            "password": password,
        }
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        job = self.cb.executeJumpscript(
            "jumpscale",
            "vfs_set_password_routeros",
            gid=fwobj.gid,
            nid=fwobj.nid,
            args=args,
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable(
                "Failed to set password. Error: %s" % (job["result"]["errormessage"])
            )
        return job["result"]

    def fw_get_openvpn_config(self, fwid, **kwargs):
        fwobj = self._getVFWObject(fwid)
        args = {"fwobject": fwobj.obj2dict()}
        job = self.cb.executeJumpscript(
            "jumpscale",
            "vfs_get_openvpn_config_routeros",
            gid=fwobj.gid,
            nid=fwobj.nid,
            args=args,
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to get OpenVPN Config")
        return job["result"]

    def fw_delete(self, fwid, deletemodel=True, timeout=600, **kwargs):
        """
        param:fwid firewall id
        param:gid grid id
        """
        fwobj = self.osisvfw.get(fwid)
        args = {"name": "%s_%s" % (fwobj.domain, fwobj.name)}
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        if fwobj.type == "routeros":
            args = {"networkid": fwobj.id}
            if fwobj.nid:
                job = self.cb.executeJumpscript(
                    "jumpscale",
                    "vfs_destroy_routeros",
                    nid=fwobj.nid,
                    gid=fwobj.gid,
                    args=args,
                    timeout=timeout,
                )
                if job["state"] != "OK":
                    raise exceptions.ServiceUnavailable(
                        "Failed to remove vfw with id %s" % fwid
                    )
                if deletemodel:
                    # delete backup if the delete is final
                    args = {
                        "ovs_connection": self.get_ovs_connection(fwobj.gid),
                        "diskpath": "/routeros/{0:04x}/routeros-small-{0:04x}.raw".format(
                            fwobj.id
                        ),
                    }
                    job = self.cb.executeJumpscript(
                        "greenitglobe",
                        "deletedisk_by_path",
                        role="storagedriver",
                        gid=fwobj.gid,
                        args=args,
                    )
                    if job["state"] != "OK":
                        raise exceptions.ServiceUnavailable(
                            "Failed to remove vfw with id %s" % fwid
                        )
        else:
            args = {"fwobject": fwobj.dump()}
            self.cb.executeJumpscript(
                "jumpscale", "vfs_delete", nid=fwobj.nid, gid=fwobj.gid, args=args
            )["result"]
        if deletemodel:
            self.osisvfw.delete(fwid)

    def fw_restore(self, fwid, targetNid=None, **kwargs):
        fwobj = self.osisvfw.get(fwid)
        update_query = {"moddate": int(time.time())}
        if targetNid:
            update_query["nid"] = targetNid
        self.osisvfw.updateSearch({"guid": fwobj.guid}, {"$set": update_query})
        args = {"networkid": fwobj.id}
        job = self.cb.executeJumpscript(
            "jumpscale", "vfs_routeros_restore", nid=fwobj.nid, gid=fwobj.gid, args=args
        )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to restore vfw")
        return job["result"]

    def fw_destroy(self, fwid):
        self.osisvfw.delete(fwid)

    def _applyconfig(self, gid, nid, args):
        fwobj = arg["fwobject"]
        fwobj["leases"], fwobj["cloud-init"] = self.cb.cloudspace.get_leases_cloudinit(
            int(fwobj["domain"])
        )
        if args["fwobject"]["type"] == "routeros":
            job = self.cb.executeJumpscript(
                "jumpscale", "vfs_applyconfig_routeros", gid=gid, nid=nid, args=args
            )
        else:
            args.pop("name")
            job = self.cb.executeJumpscript(
                "jumpscale", "vfs_applyconfig", gid=gid, nid=nid, args=args
            )

        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to apply config")
        return job["result"]

    def fw_forward_create(
        self, fwid, gid, fwip, fwport, destip, destport, protocol="tcp", **kwargs
    ):
        """
        param:fwid firewall id
        param:gid grid id
        param:fwip str,,adr on fw which will be visible to extenal world
        param:fwport str,,port on fw which will be visble to external world
        param:destip adr where we forward to e.g. a ssh server in DMZ
        param:destport port where we forward to e.g. a ssh server in DMZ
        """
        protocol = protocol or "tcp"
        with self.osisvfw.lock(fwid):
            fwobj = self._getVFWObject(fwid)
            self.osisvfw.updateSearch(
                {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
            )
            for tcprule in fwobj.tcpForwardRules:
                if (
                    tcprule.fromAddr == fwip
                    and tcprule.fromPort == str(fwport)
                    and tcprule.protocol == protocol
                ):
                    raise exceptions.Conflict(
                        "Forward to %s with port %s already exists" % (fwip, fwport)
                    )
            rule = fwobj.new_tcpForwardRule()
            rule.fromAddr = fwip
            rule.fromPort = str(fwport)
            rule.toAddr = destip
            rule.toPort = str(destport)
            rule.protocol = protocol
            self.osisvfw.updateSearch(
                {"guid": fwid}, {"$addToSet": {"tcpForwardRules": rule}}
            )
        args = {
            "name": "%s_%s" % (fwobj.domain, fwobj.name),
            "fwobject": fwobj.obj2dict(),
        }
        result = self._applyconfig(fwobj.gid, fwobj.nid, args)
        if not result:
            self.fw_forward_delete(
                fwid, gid, fwip, fwport, destip, destport, protocol, apply=False
            )
        return result

    def fw_reapply(self, fwid):
        fwobj = self._getVFWObject(fwid).obj2dict()
        self.osisvfw.updateSearch(
            {"guid": fwobj["guid"]}, {"$set": {"moddate": int(time.time())}}
        )
        args = {"name": "%(domain)s_%(name)s" % fwobj, "fwobject": fwobj}
        return self._applyconfig(fwobj["gid"], fwobj["nid"], args)

    def fw_forward_delete(
        self,
        fwid,
        gid,
        fwip,
        fwport,
        destip=None,
        destport=None,
        protocol=None,
        apply=True,
        **kwargs
    ):
        """
        param:fwid firewall id
        param:gid grid id
        param:fwip str,,adr on fw which will be visible to extenal world
        param:fwport port on fw which will be visble to external world
        param:destip adr where we forward to e.g. a ssh server in DMZ
        param:destport port where we forward to e.g. a ssh server in DMZ
        """
        with self.osisvfw.lock(fwid):
            fwobj = self._getVFWObject(fwid)
            self.osisvfw.updateSearch(
                {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
            )
            change = False
            result = False
            for rule in fwobj.tcpForwardRules:
                if rule.fromAddr == fwip and rule.fromPort == str(fwport):
                    if (
                        protocol
                        and rule.protocol
                        and rule.protocol.lower() != protocol.lower()
                    ):
                        continue
                    change = True
                    fwobj.tcpForwardRules.remove(rule)
            if change:
                self.osisvfw.set(fwobj)
        if change and apply:
            args = {
                "name": "%s_%s" % (fwobj.domain, fwobj.name),
                "fwobject": fwobj.obj2dict(),
            }
            result = self._applyconfig(fwobj.gid, fwobj.nid, args)
        return result

    def fw_forward_list(self, fwid, gid, localip=None, **kwargs):
        """
        list all portformarding rules,
        is list of list [[$fwport,$destip,$destport]]
        1 port on source can be forwarded to more ports at back in which case the FW will do loadbalancing
        param:fwid firewall id
        param:gid grid id
        """
        fwobj = self.osisvfw.get(fwid)
        result = list()
        if localip:
            for rule in fwobj.tcpForwardRules:
                if localip == rule.toAddr:
                    result.append(
                        {
                            "publicIp": rule.fromAddr,
                            "publicPort": rule.fromPort,
                            "localIp": rule.toAddr,
                            "localPort": rule.toPort,
                            "protocol": rule.protocol,
                        }
                    )
        else:
            for rule in fwobj.tcpForwardRules:
                result.append(
                    {
                        "publicIp": rule.fromAddr,
                        "publicPort": rule.fromPort,
                        "localIp": rule.toAddr,
                        "localPort": rule.toPort,
                        "protocol": rule.protocol,
                    }
                )
        return result

    def fw_list(self, gid, domain=None, **kwargs):
        """
        param:gid grid id
        param:domain if not specified then all domains
        """
        result = list()
        filter = dict()
        if domain:
            filter["domain"] = str(domain)
        if gid:
            filter["gid"] = gid
        fields = ("domain", "name", "gid", "nid", "guid")
        vfws = self.osisvfw.search(filter)[1:]
        for vfw in vfws:
            vfwdict = {}
            for field in fields:
                vfwdict[field] = vfw.get(field)
            result.append(vfwdict)
        return result

    def fw_start(self, fwid, resettype="restore", force=False, targetNid=None, **kwargs):
        """
        param:fwid firewall id
        param:gid grid id
        """
        if resettype not in ["factory", "restore"]:
            raise exceptions.BadRequest(
                "Invalid value {} for resettype".format(resettype)
            )
        if not force:
            try:
                running = self.fw_check(fwid)
            except:
                running = False
            if running:
                return True
                
        fwobj = self._getVFWObject(fwid)
        cloudspace = self.cbmodel.cloudspace.get(int(fwobj.domain))
        if cloudspace.externalnetworkip is None:
            raise exceptions.BadRequest(
                "Can not reset VFW which has no external network IP please deploy instead."
            )
        restored = False
        if resettype == "restore" and fwobj.type == "routeros":
            restored = self.fw_restore(fwid, targetNid)
        if resettype == "factory" or not restored:
            return self._fw_create(fwobj, targetNid, isnew=False)
        fwobj = self._getVFWObject(fwid)  # to get updated model
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        args = {"fwobject": fwobj.obj2dict()}
        if fwobj.type == "routeros":
            job = self.cb.executeJumpscript(
                "jumpscale",
                "vfs_start_routeros",
                gid=fwobj.gid,
                nid=fwobj.nid,
                args=args,
            )
        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to start vfw")
        self.fw_reapply(fwid)
        return job["result"]

    def fw_stop(self, fwid, **kwargs):
        """
        param:fwid firewall id
        param:gid grid id
        """
        fwobj = self._getVFWObject(fwid)
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        args = {"networkid": fwobj.id}
        if fwobj.type == "routeros":
            args = {"networkid": fwobj.id}
            job = self.cb.executeJumpscript(
                "jumpscale",
                "vfs_stop_routeros",
                gid=fwobj.gid,
                nid=fwobj.nid,
                args=args,
            )
        else:
            args = {"fwobject": fwobj.dump()}
            job = self.cb.executeJumpscript(
                "jumpscale", "vfs_delete", gid=fwobj.gid, nid=fwobj.nid, args=args
            )

        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to stop vfw")
        return job["result"]

    def fw_check(self, fwid, timeout=60, **kwargs):
        """
        will do some checks on firewall to see is running, is reachable over ssh, is connected to right interfaces
        param:fwid firewall id
        param:gid grid id
        """
        fwobj = self._getVFWObject(fwid)
        self.osisvfw.updateSearch(
            {"guid": fwobj.guid}, {"$set": {"moddate": int(time.time())}}
        )
        args = {"networkid": fwobj.id}
        if fwobj.type == "routeros":
            job = self.cb.executeJumpscript(
                "jumpscale",
                "vfs_checkstatus_routeros",
                gid=fwobj.gid,
                nid=fwobj.nid,
                args=args,
                timeout=timeout,
            )
        else:
            args = {"fwobject": fwobj.dump()}
            job = self.cb.executeJumpscript(
                "jumpscale", "vfs_checkstatus", gid=fwobj.gid, nid=fwobj.nid, args=args
            )

        if job["state"] != "OK":
            raise exceptions.ServiceUnavailable("Failed to get vfw status")
        return job["result"]
