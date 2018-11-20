# Add extra specific cloudscaler functions for libvirt libcloud driver
from JumpScale import j
from CloudscalerLibcloud.utils import connection
from CloudscalerLibcloud.utils.gridconfig import GridConfig
from libcloud.compute.base import Node, NodeState, StorageVolume
from libcloud.compute.drivers.dummy import DummyNodeDriver
from jinja2 import Environment, PackageLoader
from JumpScale.portal.portal import exceptions
from xml.etree import ElementTree
from cloudbrokerlib.utils import getJobTags
import urlparse
import uuid
import crypt
import random
import string
import yaml
import datetime

baselength = len(string.lowercase)
env = Environment(loader=PackageLoader("CloudscalerLibcloud", "templates"))
vmlog_dir = "/var/log/ovc/vms"


class LibvirtState:
    RUNNING = 1
    HALTED = 5


class StorageException(Exception):
    def __init__(self, message, e, volumes=None):
        super(StorageException, self).__init__(message)
        self.origexception = e
        self.volumes = volumes or []

    def __str__(self):
        return "{}, {}".format(self.message, self.origexception)


class NotEnoughResources(exceptions.ServiceUnavailable):
    def __init__(self, message, volumes=None):
        super(NotEnoughResources, self).__init__(message)
        self.volumes = volumes


def convertnumber(number):
    output = ""
    if number == 0:
        return string.lowercase[0]
    segment = number // baselength
    remainder = number % baselength
    if segment > 0:
        output += convertnumber(segment - 1)
    output += string.lowercase[remainder]

    return output


def convertchar(word):
    number = 0
    word = list(reversed(word))
    for idx in xrange(len(word) - 1, -1, -1):
        addme = 1 if idx != 0 else 0
        number += (addme + string.lowercase.index(word[idx])) * baselength ** idx
    return number


def getOpenvStroageVolumeId(
    host, port, name, vdiskguid, transport="tcp", username=None, password=None
):
    url = "openvstorage+{transport}://{host}:{port}/{name}".format(
        transport=transport, host=host, port=port, name=name
    )
    if username and password:
        url += ":username={}:password={}".format(username, password)
    url += "@{}".format(vdiskguid)
    return url


class NetworkInterface(object):
    def __init__(self, mac, target, type, bridgename, networkId=None):
        self.mac = mac
        self.target = target
        self.type = type
        self.networkId = networkId
        self.bridgename = bridgename

    def __str__(self):
        template = env.get_template("interface.xml")
        return template.render(self.__dict__)


class OpenvStorageVolume(StorageVolume):
    def __init__(self, id, *args, **kwargs):
        self.iotune = kwargs.pop("iotune", {})
        order = kwargs.pop("order", 0) or 0
        self._id = None
        super(OpenvStorageVolume, self).__init__(id, *args, **kwargs)
        self.id = id  # force id setter after init
        self.type = "disk"
        self.bus = "virtio"
        self.dev = "vd{}".format(convertnumber(order))

    @property
    def ovsurl(self):
        ovsurl = "openvstorage+{}:{}:{}/{}".format(
            self.edgetransport, self.edgehost, self.edgeport, self.name
        )
        if self.username:
            ovsurl += ":username={}:password={}".format(self.username, self.password)
        return ovsurl

    def __str__(self):
        template = env.get_template("ovsdisk.xml")
        return template.render(self.__dict__)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = value
        if value:
            vdiskid, _, vdiskguid = value.partition("@")
            url = urlparse.urlparse(vdiskid)
            self.vdiskguid = vdiskguid
            self.edgetransport = (
                "tcp" if "+" not in url.scheme else url.scheme.split("+")[1]
            )
            self.edgehost = url.hostname
            self.edgeport = url.port
            pathparams = url.path.strip("/").split(":")
            self.username = None
            self.password = None
            self.name = pathparams[0]
            for param in pathparams[1:]:
                key, sep, val = param.partition("=")
                if sep == "=":
                    if key == "username":
                        self.username = val
                    elif key == "password":
                        self.password = val


class PhysicalVolume(StorageVolume):
    def __init__(self, *args, **kwargs):
        self.iotune = kwargs.pop("iotune", {})
        order = kwargs.pop("order", 0)
        super(PhysicalVolume, self).__init__(*args, **kwargs)
        self.source = urlparse.urlparse(self.id).path
        self.type = "disk"
        self.bus = "virtio"
        self.dev = "vd{}".format(convertnumber(order))

    def __str__(self):
        template = env.get_template("phydisk.xml")
        return template.render(self.__dict__)


class OpenvStorageISO(OpenvStorageVolume):
    def __init__(self, *args, **kwargs):
        super(OpenvStorageISO, self).__init__(*args, **kwargs)
        self.dev = "hdc"
        self.type = "cdrom"
        self.bus = "ide"


def OpenvStorageVolumeFromXML(disk, driver):
    source = disk.find("source")
    name = source.attrib.get("name")
    host = source.find("host")
    vdiskguid = source.attrib.get("vdiskguid")
    hostname = host.attrib.get("name")
    hostport = host.attrib.get("port")
    transport = host.attrib.get("transport", "tcp")
    url = getOpenvStroageVolumeId(
        host=hostname,
        port=hostport,
        name=name,
        transport=transport,
        vdiskguid=vdiskguid,
        username=source.attrib.get("username"),
        password=source.attrib.get("passwd"),
    )
    return OpenvStorageVolume(id=url, name="N/A", size=0, driver=driver)


class CSLibvirtNodeDriver(object):

    _ovsdata = {}
    type = "CSLibvirt"

    NODE_STATE_MAP = {
        0: NodeState.TERMINATED,
        1: NodeState.RUNNING,
        2: NodeState.PENDING,
        3: NodeState.TERMINATED,  # paused
        4: NodeState.TERMINATED,  # shutting down
        5: NodeState.TERMINATED,
        6: NodeState.UNKNOWN,  # crashed
        7: NodeState.UNKNOWN,  # last
    }

    def __init__(self, stack):
        self._rndrbn_vnc = 0
        self.id = int(stack.referenceId)
        self.gid = stack.gid
        self.name = "libvirt"
        self.uri = stack.apiUrl
        self.stack = stack
        self.env = env
        self.scl = j.clients.osis.getNamespace("system")
        grid = self.scl.grid.get(self.gid)
        self.node = self.scl.node.get(self.id)
        self.config = GridConfig(grid, self.node.memory / 1024.)
        # preload ovs_credentials and ovs_connection
        # this is to detect erors earlier if there is
        # some misconfiguration
        self.ovs_connection

    backendconnection = connection.DummyConnection()

    @property
    def ovs_credentials(self):
        cachekey = "credentials_{}".format(self.gid)
        if cachekey not in self._ovsdata:
            credentials = self.config.get("ovs_credentials")
            self._ovsdata[cachekey] = credentials
        return self._ovsdata[cachekey]

    @property
    def ovs_connection(self):
        cachekey = "ovs_connection_{}".format(self.gid)
        if cachekey not in self._ovsdata:
            connection = {
                "ips": self.ovs_credentials["ips"],
                "client_id": self.ovs_credentials["client_id"],
                "client_secret": self.ovs_credentials["client_secret"],
            }
            self._ovsdata[cachekey] = connection
        return self._ovsdata[cachekey]

    @property
    def ovs_settings(self):
        cachekey = "ovs_settings_{}".format(self.gid)
        if cachekey not in self._ovsdata:
            grid_settings = self.config.get("ovs_settings", dict())
            settings = dict(
                vpool_vmstor_metadatacache=grid_settings.get(
                    "vpool_vmstor_metadatacache", 20
                ),
                vpool_data_metadatacache=grid_settings.get(
                    "vpool_data_metadatacache", 20
                ),
            )
            self._ovsdata[cachekey] = settings
        return self._ovsdata[cachekey]

    def getVolumeId(self, vdiskguid, edgeclient, name):
        username = self.ovs_credentials.get("edgeuser")
        password = self.ovs_credentials.get("edgepassword")
        return getOpenvStroageVolumeId(
            edgeclient["storageip"],
            edgeclient["edgeport"],
            name,
            vdiskguid,
            edgeclient.get("protocol", "tcp"),
            username,
            password,
        )

    @property
    def all_edgeclients(self):
        return self._execute_agent_job(
            "listedgeclients", role="storagemaster", ovs_connection=self.ovs_connection
        )

    def list_vdisks(self, storagerouterguid):
        return self._execute_agent_job(
            "listvdisks",
            role="storagemaster",
            ovs_connection=self.ovs_connection,
            storagerouterguid=storagerouterguid,
        )

    @property
    def edgeclients(self):
        edgeclients = filter(
            lambda client: client["status"] == "OK", self.all_edgeclients
        )

        activesessions = (
            self.backendconnection.agentcontroller_client.listActiveSessions()
        )
        activenodes = self.scl.node.search(
            {"status": "ENABLED", "gid": self.gid, "roles": "storagedriver"}
        )[1:]

        def get_active_node(storageip):
            for activenode in activenodes:
                if storageip in activenode["ipaddr"]:
                    return activenode
            return None

        def filter_clients(client):
            node = get_active_node(client["storageip"])
            if node is None:
                return False
            client["nid"] = node["id"]
            return (node["gid"], node["id"]) in activesessions

        return filter(filter_clients, edgeclients)

    def getNextEdgeClient(self, vpool, edgeclients=None):
        clients = edgeclients or self.edgeclients[:]
        clients = filter(lambda x: x["vpool"] == vpool, clients)
        if not clients:
            raise exceptions.ServiceUnavailable(
                "No storagerouter available for vpool {}".format(vpool)
            )
        return sorted(clients, key=lambda client: client["vdiskcount"])[0]

    def getEdgeClientFromVolume(self, volume):
        edgeclients = self.edgeclients[:]
        for edgeclient in edgeclients:
            if (
                volume.edgehost == edgeclient["storageip"]
                and volume.edgeport == edgeclient["edgeport"]
            ):
                return edgeclient, edgeclients

    def getBestDataVpool(self):
        edgeclients = self.edgeclients[:]
        diskspervpool = {}
        for edgeclient in edgeclients:
            diskspervpool[edgeclient["vpool"]] = (
                diskspervpool.setdefault(edgeclient["vpool"], 0)
                + edgeclient["vdiskcount"]
            )
        if len(diskspervpool) > 1:
            for vpool in list(diskspervpool.keys()):
                if not vpool.startswith("data"):
                    diskspervpool.pop(vpool)
        # get vpool with least vdiskcount
        return (
            sorted(diskspervpool.items(), key=lambda vpool: vpool[1])[0][0],
            edgeclients,
        )

    def set_backend(self, connection):
        """
        Set a connection to the cloudbroker backend, this is used
        to get all the supported images and sizes
        """
        self.backendconnection = connection

    def _execute_agent_job(
        self, name_, id=None, wait=True, queue=None, role=None, timeout=600, **kwargs
    ):
        if not id and not role:
            id = int(self.id)

        elif id is None:
            id = 0
        else:
            id = id and int(id)

        tags = getJobTags()
        job = self.backendconnection.agentcontroller_client.executeJumpscript(
            "greenitglobe",
            name_,
            nid=id,
            role=role,
            gid=self.gid,
            wait=wait,
            queue=queue,
            args=kwargs,
            tags=tags,
        )
        if wait and job["state"] != "OK":
            if job["state"] == "NOWORK":
                j.errorconditionhandler.raiseOperationalWarning(
                    "Could not find agent with nid:%s" % id
                )
            elif job["state"] == "TIMEOUT":
                j.errorconditionhandler.raiseOperationalWarning(
                    "Job failed to execute on time"
                )
            else:
                j.errorconditionhandler.raiseOperationalWarning(
                    "Could not execute %s for nid:%s, error was:%s"
                    % (name_, id, job["result"])
                )

            raise exceptions.ServiceUnavailable(
                "Could not perform action: {name} at this time".format(name=name_)
            )
        if wait:
            return job["result"]
        else:
            return job

    def _create_disk(self, vm_id, disksize, image, disk_role="base"):
        edgeclient = self.getNextEdgeClient("vmstor")

        diskname = "{0}/bootdisk-{0}".format(vm_id)
        kwargs = {
            "ovs_connection": self.ovs_connection,
            "storagerouterguid": edgeclient["storagerouterguid"],
            "size": disksize,
            "templateguid": image.referenceId,
            "diskname": diskname,
            "pagecache_ratio": self.ovs_settings["vpool_vmstor_metadatacache"],
        }

        try:
            vdiskguid = self._execute_agent_job(
                "creatediskfromtemplate", role="storagedriver", **kwargs
            )
        except (Exception, exceptions.ServiceUnavailable) as ex:
            raise StorageException(ex.message, ex)

        volumeid = self.getVolumeId(
            vdiskguid=vdiskguid, edgeclient=edgeclient, name=diskname
        )
        return (
            OpenvStorageVolume(id=volumeid, name=diskname, size=disksize, driver=self),
            edgeclient,
        )

    def create_volume(self, size, name, data=True, dev=""):
        if data:
            vpoolname, edgeclients = self.getBestDataVpool()
            edgeclient = self.getNextEdgeClient(vpoolname, edgeclients)
            diskname = "volumes/volume_{}".format(name)
        else:
            edgeclient = self.getNextEdgeClient("vmstor")
            diskname = name
        kwargs = {
            "ovs_connection": self.ovs_connection,
            "vpoolguid": edgeclient["vpoolguid"],
            "storagerouterguid": edgeclient["storagerouterguid"],
            "diskname": diskname,
            "size": size,
            "pagecache_ratio": self.ovs_settings["vpool_data_metadatacache"],
        }
        try:
            vdiskguid = self._execute_agent_job(
                "createdisk", role="storagedriver", **kwargs
            )
        except (Exception, exceptions.ServiceUnavailable) as ex:
            raise StorageException(ex.message, ex)
        volumeid = self.getVolumeId(
            vdiskguid=vdiskguid, edgeclient=edgeclient, name=diskname
        )
        stvol = OpenvStorageVolume(id=volumeid, size=size, name=diskname, driver=self)
        stvol.dev = dev
        return stvol

    def create_volumes(self, volumes):
        stvolumes = []
        for volume in volumes:
            stvol = self.create_volume(
                volume["size"],
                volume["name"],
                volume.get("data", True),
                volume.get("dev", ""),
            )
            stvolumes.append(stvol)
        return stvolumes

    def attach_volume(self, node, volume):
        self._execute_agent_job(
            "attach_device", queue="hypervisor", xml=str(volume), machineid=node.id
        )
        return True

    def destroy_volume(self, volume):
        return self.destroy_volumes_by_guid([volume.vdiskguid])

    def get_volume_from_xml(self, xmldom, volume):
        devices = xmldom.find("devices")
        for disk in devices.iterfind("disk"):
            if disk.attrib["device"] != "disk":
                continue
            source = disk.find("source")
            if source.attrib.get("dev", source.attrib.get("name")) == volume.name:
                return devices, disk
        return None, None

    def detach_volume(self, volume):
        node = volume.extra["node"]
        self._execute_agent_job(
            "detach_device", queue="hypervisor", xml=str(volume), machineid=node.id
        )
        return node

    def _create_metadata_iso(self, edgeclient, name, password, type, userdata=None):
        customuserdata = userdata or {}
        if isinstance(customuserdata, basestring):
            customuserdata = yaml.load(customuserdata)
        if type not in ["WINDOWS", "Windows"]:
            memrule = 'SUBSYSTEM=="memory", ACTION=="add", TEST=="state", ATTR{state}=="offline", ATTR{state}="online"'
            cpurule = 'SUBSYSTEM=="cpu", ACTION=="add", TEST=="online", ATTR{online}=="0", ATTR{online}="1"'
            runcmds = []
            runcmds.append(
                "echo '{}' > /etc/udev/rules.d/66-hotplug.rules".format(memrule)
            )
            runcmds.append(
                "echo '{}' >> /etc/udev/rules.d/66-hotplug.rules".format(cpurule)
            )
            runcmds.append(["udevadm", "control", "-R"])

            userdata = {
                "password": password,
                "users": [
                    {
                        "name": "cloudscalers",
                        "plain_text_passwd": password,
                        "lock-passwd": False,
                        "shell": "/bin/bash",
                        "sudo": "ALL=(ALL) ALL",
                    }
                ],
                "ssh_pwauth": True,
                "runcmd": runcmds,
                "manage_etc_hosts": True,
                "chpasswd": {"expire": False},
            }
            metadata = {"local-hostname": name}
            if "users" in customuserdata:
                users = customuserdata.pop("users", [])
                userdata["users"].extend(users)
            userdata.update(customuserdata)
        else:
            userdata = {}
            metadata = {"admin_pass": password, "hostname": name}

        diskpath = "{0}/cloud-init-{0}".format(name)
        kwargs = {
            "ovs_connection": self.ovs_connection,
            "vpoolguid": edgeclient["vpoolguid"],
            "storagerouterguid": edgeclient["storagerouterguid"],
            "diskname": diskpath,
            "size": 0.1,
            "pagecache_ratio": self.ovs_settings["vpool_data_metadatacache"],
        }
        try:
            vdiskguid = self._execute_agent_job(
                "createdisk", role="storagedriver", **kwargs
            )
        except Exception as ex:
            raise StorageException(ex.message, ex)

        volumeid = self.getVolumeId(
            vdiskguid=vdiskguid, edgeclient=edgeclient, name=diskpath
        )
        isovolume = OpenvStorageISO(id=volumeid, name=diskpath, size=0, driver=self)
        try:
            volumeid = self._execute_agent_job(
                "createmetaiso",
                role="storagedriver",
                ovspath=volumeid,
                metadata=metadata,
                userdata=userdata,
                type=type,
            )
        except Exception as ex:
            raise StorageException(ex.message, ex, volumes=[isovolume])
        return isovolume

    def generate_password_hash(self, password):
        def generate_salt():
            salt_set = (
                "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789./"
            )
            salt = 16 * " "
            return "".join([random.choice(salt_set) for c in salt])

        salt = generate_salt()
        return crypt.crypt(password, "$6$" + salt)

    def get_host_memory(self):
        return self.node.memory - self.config.get("reserved_mem")

    def init_node(
        self,
        name,
        size,
        networkid=None,
        volumes=None,
        imagetype="",
        boottype="bios",
        machineId=None,
    ):
        volumes = volumes or []
        macaddress = self.backendconnection.getMacAddress(self.gid)

        networkname = "space_{:04x}".format(networkid)
        nodeid = str(uuid.uuid4())
        interfaces = [
            NetworkInterface(
                macaddress, "{}-{:04x}".format(name, networkid), "bridge", networkname
            )
        ]
        netinfo = [{"id": networkid, "type": "vxlan"}]
        extra = {
            "volumes": volumes,
            "ifaces": interfaces,
            "imagetype": imagetype,
            "size": size,
            "bootdev": "hd",
            "boottype": boottype,
            "machineId": machineId,
        }
        node = Node(
            id=nodeid,
            name=name,
            state=NodeState.PENDING,
            public_ips=[],
            private_ips=[],
            driver=self,
            extra=extra,
        )
        machinexml = self.get_xml(node)

        # 0 means default behaviour, e.g machine is auto started.
        result = self._execute_agent_job(
            "createmachine",
            queue="hypervisor",
            machinexml=machinexml,
            vmlog_dir=vmlog_dir,
            netinfo=netinfo,
        )
        if not result or result == -1:
            # Agent is not registered to agentcontroller or we can't provision the
            # machine(e.g not enough resources, delete machine)
            if result == -1:
                self._execute_agent_job(
                    "deletemachine",
                    queue="hypervisor",
                    machineid=None,
                    machinexml=machinexml,
                )
            raise NotEnoughResources("Failed to create machine", volumes)

        node = self._from_agent_to_node(result, volumes=volumes)
        return node

    def ex_create_template(self, node, name, new_vdiskguid):
        bootvolume = node.extra["volumes"][0]
        kwargs = {
            "ovs_connection": self.ovs_connection,
            "diskguid": bootvolume.vdiskguid,
            "new_vdiskguid": new_vdiskguid,
            "template_name": name,
        }
        image_path = self._execute_agent_job(
            "createtemplate", queue="io", role="storagedriver", **kwargs
        )
        return image_path

    def ex_delete_template(self, templateid):
        kwargs = {
            "ovs_connection": self.ovs_connection,
            "diskguid": str(uuid.UUID(templateid)),
        }
        self._execute_agent_job(
            "deletetemplate", queue="io", role="storagedriver", **kwargs
        )

    def ex_get_node_details(self, node_id):
        driver = DummyNodeDriver(0)
        node = Node(
            id=node_id,
            name="",
            state=NodeState.RUNNING,
            public_ips=[],
            private_ips=[],
            driver=driver,
        )
        agentnode = self._get_domain_for_node(node)
        if agentnode is None:
            return None
        node = self._from_agent_to_node(agentnode)
        return node

    def get_disk_guids(self, node, type=None):
        diskguids = []
        for volume in node.extra["volumes"]:
            if (
                type is not None
                and volume.type != type
                or isinstance(volume, PhysicalVolume)
            ):
                continue
            diskguids.append(volume.vdiskguid)
        return diskguids

    def ex_create_snapshot(self, node, name):
        diskguids = self.get_disk_guids(node, type="disk")
        kwargs = {
            "diskguids": diskguids,
            "ovs_connection": self.ovs_connection,
            "name": name,
        }
        return self._execute_agent_job(
            "createsnapshots", role="storagedriver", **kwargs
        )

    def ex_list_snapshots(self, node):
        diskguids = self.get_disk_guids(node, type="disk")
        kwargs = {"diskguids": diskguids, "ovs_connection": self.ovs_connection}
        return self._execute_agent_job("listsnapshots", role="storagedriver", **kwargs)

    def ex_delete_snapshot(self, node, timestamp=None, name=None):
        diskguids = self.get_disk_guids(node, type="disk")
        kwargs = {
            "diskguids": diskguids,
            "ovs_connection": self.ovs_connection,
            "timestamp": timestamp,
            "name": name,
        }
        return self._execute_agent_job(
            "deletesnapshot", wait=False, role="storagedriver", **kwargs
        )

    def ex_rollback_snapshot(self, node, timestamp, name):
        diskguids = self.get_disk_guids(node, type="disk")
        kwargs = {
            "diskguids": diskguids,
            "timestamp": timestamp,
            "name": name,
            "ovs_connection": self.ovs_connection,
        }
        return self._execute_agent_job(
            "rollbacksnapshot", role="storagedriver", **kwargs
        )

    def _get_domain_disk_file_names(self, dom, disktype="disk"):
        if isinstance(dom, ElementTree.Element):
            xml = dom
        elif isinstance(dom, basestring):
            xml = ElementTree.fromstring(dom)
        else:
            raise RuntimeError("Invalid type %s for parameter dom" % type(dom))
        disks = xml.findall("devices/disk")
        diskfiles = list()
        for disk in disks:
            if disktype is None or disk.attrib["device"] == disktype:
                source = disk.find("source")
                if source is not None:
                    if source.attrib.get("protocol") == "openvstorage":
                        ovsdisk = OpenvStorageVolumeFromXML(disk, self)
                        diskfiles.append(ovsdisk.vdiskguid)
                    elif "dev" in source.attrib:
                        diskfiles.append(source.attrib["dev"])
                    elif "file" in source.attrib:
                        diskfiles.append(source.attrib["file"])
        return diskfiles

    def _get_snapshot_disk_file_names(self, xml):
        xml = ElementTree.fromstring(xml)
        domain = xml.findall("domain")[0]
        return self._get_domain_disk_file_names(domain)

    def destroy_node(self, node):
        xml = self.get_xml(node)
        self._execute_agent_job(
            "deletemachine", queue="hypervisor", machineid=node.id, machinexml=xml
        )
        return True

    def ex_limitio(self, volume):
        node = volume.extra["node"]
        if node.state == LibvirtState.RUNNING:
            return self._execute_agent_job(
                "limitdiskio",
                queue="hypervisor",
                machineid=node.id,
                disks=[volume.id],
                iotune=volume.iotune,
            )

    def destroy_volumes_by_guid(self, diskguids):
        kwargs = {"diskguids": diskguids, "ovs_connection": self.ovs_connection}
        try:
            self._execute_agent_job("deletedisks", role="storagedriver", **kwargs)
        except exceptions.ServiceUnavailable as rError:
            j.errorconditionhandler.processPythonExceptionObject(
                rError,
                message="Failed to delete disks may be they are deleted from the storage node",
            )

    def ex_get_console_url(self, node):
        urls = self.backendconnection.listVNC(self.gid)
        id_ = self._rndrbn_vnc % len(urls)
        url = urls[id_]
        self._rndrbn_vnc += 1
        token = self.backendconnection.storeInfo(self.ex_get_console_output(node), 300)
        return url + "%s" % token

    def list_nodes(self):
        noderesult = []
        nodes = self.backendconnection.listNodes()
        result = self._execute_agent_job("listmachines", queue="default")
        for x in result:
            if x["id"] in nodes:
                ipaddress = nodes[x["id"]]["ipaddress"]
            else:
                ipaddress = ""
            noderesult.append(self._from_agent_to_node(x, ipaddress))
        return noderesult

    def ex_stop_node(self, node, force=False):
        machineid = node.id
        return self._execute_agent_job(
            "stopmachine", queue="hypervisor", machineid=machineid, force=force
        )

    def ex_suspend_node(self, node):
        machineid = node.id
        return self._execute_agent_job(
            "suspendmachine", queue="hypervisor", machineid=machineid
        )

    def ex_resume_node(self, node):
        machineid = node.id
        return self._execute_agent_job(
            "resumemachine", queue="hypervisor", machineid=machineid
        )

    def ex_pause_node(self, node):
        machineid = node.id
        return self._execute_agent_job(
            "pausemachine", queue="hypervisor", machineid=machineid
        )

    def ex_unpause_node(self, node):
        machineid = node.id
        return self._execute_agent_job(
            "unpausemachine", queue="hypervisor", machineid=machineid
        )

    def ex_soft_reboot_node(self, node):
        xml = self.get_xml(node)
        netinfo = self.get_net_info(node)
        return self._execute_agent_job(
            "softrebootmachine",
            queue="hypervisor",
            machineid=node.id,
            xml=xml,
            netinfo=netinfo,
        )

    def ex_hard_reboot_node(self, node):
        xml = self.get_xml(node)
        netinfo = self.get_net_info(node)
        return self._execute_agent_job(
            "hardrebootmachine",
            queue="hypervisor",
            machineid=node.id,
            xml=xml,
            netinfo=netinfo,
        )

    def get_net_info(self, node):
        netinfo = []
        for interface in node.extra["ifaces"]:
            if interface.type == "private":
                netinfo.append({"type": "vxlan", "id": interface.networkId})
            else:
                netinfo.append({"type": "vlan", "id": interface.networkId})
        return netinfo

    def get_xml(self, node):
        machinetemplate = self.env.get_template("machine.xml")
        hostmemory = self.get_host_memory()
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        logfile = "{logdir}/{id}.{timestamp}.log".format(
            logdir=vmlog_dir,
            id=node.extra.get("machineId", node.id),
            timestamp=timestamp,
        )
        machinexml = machinetemplate.render(
            {"node": node, "hostmemory": hostmemory, "logfile": logfile}
        )
        return machinexml

    def ex_start_node(self, node):
        machinexml = self.get_xml(node)
        netinfo = self.get_net_info(node)
        self._execute_agent_job(
            "startmachine",
            queue="hypervisor",
            machineid=node.id,
            xml=machinexml,
            vmlog_dir=vmlog_dir,
            netinfo=netinfo,
        )
        return True

    def ex_get_console_output(self, node):
        domain = self._get_domain_for_node(node=node)
        xml = ElementTree.fromstring(domain["XMLDesc"])
        graphics = xml.find("devices/graphics")
        info = dict()
        info["port"] = int(graphics.attrib["port"])
        info["type"] = graphics.attrib["type"]
        info["ipaddress"] = self._get_connection_ip()
        return info

    def ex_import(self, size, vmid, networkid, disks):
        name = "vm-%s" % vmid
        volumes = []
        for i, disk in enumerate(disks):
            volume = OpenvStorageVolume(
                id=disk["referenceId"],
                name="N/A",
                size=disk["size"],
                driver=self,
            )
            volume.dev = "vd%s" % convertnumber(i + 1)
            volumes.append(volume)
        return self.init_node(
            name, size, networkid=networkid, volumes=volumes, machineId=vmid
        )

    def ex_clone_disks(self, diskmapping, disks_snapshots=None):
        disks_snapshots = disks_snapshots or {}
        disks = []
        diskvpool = {}
        for volume, diskname in diskmapping:
            source_edgeclient, edgeclients = self.getEdgeClientFromVolume(volume)
            edgeclient = self.getNextEdgeClient(source_edgeclient["vpool"], edgeclients)
            diskinfo = {
                "clone_name": diskname,
                "diskguid": volume.vdiskguid,
                "storagerouterguid": edgeclient["storagerouterguid"],
            }
            if disks_snapshots.get(volume.vdiskguid, None):
                diskinfo["snapshotguid"] = disks_snapshots[volume.vdiskguid]
            diskvpool[volume.vdiskguid] = edgeclient
            disks.append(diskinfo)

        kwargs = {"ovs_connection": self.ovs_connection, "disks": disks}
        newdisks = self._execute_agent_job("clonedisks", role="storagedriver", **kwargs)
        volumes = []
        for idx, diskinfo in enumerate(disks):
            newdiskguid, vpoolguid = newdisks[idx]
            edgeclient = diskvpool[diskinfo["diskguid"]]
            volumeid = self.getVolumeId(newdiskguid, edgeclient, diskinfo["clone_name"])
            volume = OpenvStorageVolume(id=volumeid, name="N/A", size=-1, driver=self)
            volume.dev = "vd%s" % convertnumber(idx)
            volume.edgeclient = edgeclient
            volumes.append(volume)
        return volumes

    def ex_clone(
        self,
        node,
        password,
        imagetype,
        size,
        vmid,
        networkid,
        diskmapping,
        disks_snapshots=None,
    ):
        disks_snapshots = disks_snapshots or {}
        name = "vm-%s" % vmid
        volumes = self.ex_clone_disks(diskmapping, disks_snapshots)
        volumes.append(
            self._create_metadata_iso(volumes[0].edgeclient, name, password, imagetype)
        )
        return self.init_node(
            name,
            size,
            networkid=networkid,
            volumes=volumes,
            imagetype=imagetype,
            machineId=vmid,
        )

    def ex_extend_disk(self, diskguid, newsize, disk_info=None):
        if disk_info is None:
            disk_info = {"machineRefId": None}
        res = self._execute_agent_job(
            "extend_disk",
            ovs_connection=self.ovs_connection,
            size=newsize,
            diskguid=diskguid,
            disk_info=disk_info,
        )
        return res

    def ex_export(self, node, exportname, uncpath, emailaddress):
        machineid = node.id
        return self._execute_agent_job(
            "backupmachine",
            wait=False,
            machineid=machineid,
            backupname=exportname,
            location=uncpath,
            emailaddress=emailaddress,
        )

    def ex_is_storage_action_running(self, node):
        """
        Check if an action is being running that is doing some interactions
        with the disk
        """
        machineid = node.id
        return self._execute_agent_job(
            "checkstorageaction", wait=True, machineid=machineid
        )

    def _get_connection_ip(self):
        uri = urlparse.urlparse(self.uri)
        return uri.netloc

    def _get_domain_for_node(self, node):
        return self._execute_agent_job(
            "getmachine", queue="hypervisor", machineid=node.id
        )

    def _from_agent_to_node(self, domain, publicipaddress="", volumes=None):
        xml = domain.get("XMLDesc")
        node = Node(
            id=domain["id"],
            public_ips=[],
            name=domain["name"],
            private_ips=[],
            state=domain["state"],
            driver=self,
        )
        if xml:
            node = self._from_xml_to_node(xml, node)
        node.state = domain["state"]
        extra = domain["extra"]
        node.extra.update(extra)
        if volumes:
            node.extra["volumes"] = volumes
        if publicipaddress:
            node.public_ips.append(publicipaddress)
        return node

    def _from_xml_to_node(self, xml, node=None):
        dom = ElementTree.fromstring(xml)
        state = NodeState.UNKNOWN
        volumes = list()
        ifaces = list()
        for disk in dom.findall("devices/disk"):
            source = disk.find("source")
            if disk.attrib["device"] != "disk" or source.attrib.get("dev"):
                continue
            volume = OpenvStorageVolumeFromXML(disk, self)
            volumes.append(volume)
        for nic in dom.findall("devices/interface"):
            mac = None
            macelement = nic.find("mac")
            source = nic.find("source")
            if macelement is not None:
                mac = macelement.attrib["address"]
            target = nic.find("target").attrib["dev"]
            bridgename = (
                source.attrib["bridge"]
                if source.attrib.get("bridge")
                else source.attrib["network"]
            )
            if bridgename.startswith(("ext-", "public")):
                bridgetype = "PUBLIC"
            else:
                bridgetype = "bridge"
            ifaces.append(
                NetworkInterface(
                    mac=mac, target=target, type=bridgetype, bridgename=bridgename
                )
            )
        name = dom.find("name").text
        bootdev = dom.find("os/boot").attrib["dev"]
        extra = {"volumes": volumes, "ifaces": ifaces, "bootdev": bootdev}
        if node is None:
            id = dom.find("uuid").text
            node = Node(
                id=id,
                name=name,
                state=state,
                public_ips=[],
                private_ips=[],
                driver=self,
                extra=extra,
            )
        else:
            node.extra.update(extra)
        return node

    def ex_snapshots_can_be_deleted_while_running(self):
        """
        FOR LIBVIRT A SNAPSHOT CAN'T BE DELETED WHILE MACHINE RUNNGIN
        """
        return False

    def attach_public_network(self, node, vlan, ipcidr, externalNetworkId):
        """
        Attach Virtual machine to the cpu node public network
        """
        macaddress = self.backendconnection.getMacAddress(self.gid)
        target = "%s-%s-ext" % (node.name, externalNetworkId)
        bridgename = j.system.ovsnetconfig.getVlanBridge(vlan)
        interface = NetworkInterface(
            mac=macaddress,
            target=target,
            type="PUBLIC",
            bridgename=bridgename,
            networkId=vlan,
        )
        self._execute_agent_job(
            "attach_device",
            queue="hypervisor",
            xml=str(interface),
            machineid=node.id,
            ipcidr=ipcidr,
            vlan=vlan
        )
        return interface

    def detach_public_network(self, node, mac):
        for iface in node.extra["ifaces"]:
            if iface.type == "PUBLIC" and iface.mac == mac:
                self._execute_agent_job(
                    "detach_device",
                    queue="hypervisor",
                    xml=str(iface),
                    machineid=node.id,
                )

    def ex_resize(self, node, extramem, vcpus):
        machinetemplate = self.env.get_template("memory.xml")
        result = True
        if extramem > 0:
            memory = machinetemplate.render({"memory": extramem})
            result = (
                self._execute_agent_job(
                    "attach_device", queue="hypervisor", xml=memory, machineid=node.id
                )
                is not False
            )
        if vcpus is not None:
            result &= self._execute_agent_job(
                "change_vcpus", queue="hypervisor", vcpus=vcpus, machineid=node.id
            )

        if result is False:
            return False
        return True

    def ex_migrate(self, node, sourceprovider, force=False):
        domainxml = self.get_xml(node)
        netinfo = self.get_net_info(node)
        return self._execute_agent_job(
            "vm_livemigrate",
            vm_id=node.id,
            sourceurl=sourceprovider.uri,
            force=force,
            domainxml=domainxml,
            vmlog_dir=vmlog_dir,
            netinfo=netinfo,
        )
