from JumpScale import j
import sys
import random
import os
import time
import urlparse
import subprocess
import tempfile
from glob import glob

sys.path.append("/opt/OpenvStorage")
from ovs.lib.vdisk import VDiskController
from ovs.dal.lists.vdisklist import VDiskList
from ovs.dal.lists.vpoollist import VPoolList
from ovs.dal.lists.storagerouterlist import StorageRouterList
from ovs.dal.lists.storagedriverlist import StorageDriverList

CREDENTIALS = []
VPOOLNAME = "vmstor"
MESSAGETYPE = {
    "error": "ERROR",
    "success": "OK",
    "warning": "WARNING",
    "exception": "ERROR",
    "skip": "SKIPPED",
}


def setAsTemplate(templatepath):
    disk = getVDisk(templatepath, timeout=60)
    if not disk:
        raise RuntimeError(
            "Template did not become available on OVS at %s" % templatepath
        )
    if disk.info["object_type"] != "TEMPLATE":
        VDiskController.set_as_template(disk.guid)
    return disk.guid


def run_healthcheck(modulename, testname, category):
    from ovs.extensions.healthcheck.expose_to_cli import HealthCheckCLIRunner

    results = []
    try:
        hcresults = HealthCheckCLIRunner.run_method(modulename, testname)
        if not hcresults:
            return results
        for testcategory, messageinfo in hcresults["result"].iteritems():
            for state, messages in messageinfo["messages"].iteritems():
                for message in messages:
                    results.append(
                        dict(
                            state=MESSAGETYPE.get(state),
                            message=message["message"],
                            uid=message["message"],
                            category=category,
                        )
                    )
    except Exception as e:
        eco = j.errorconditionhandler.processPythonExceptionObject(e)
        msg = "Failure in check see [eco|/grid/error condition?id={}]".format(eco.guid)
        results.append({"message": msg, "category": category, "state": "ERROR"})
    return results


def listEdgeclients():
    edgeclients = []
    protocol = getEdgeProtocol()
    for storagerouter in StorageRouterList.get_storagerouters():
        if storagerouter.status == "FAILURE":
            continue
        for storagedriver in storagerouter.storagedrivers:
            edgeclient = {
                "vpool": storagedriver.vpool.name,
                "protocol": protocol,
                "ip": storagerouter.ip,
                "port": storagedriver.ports["edge"],
            }
            edgeclients.append(edgeclient)
    return edgeclients


def getEdgeProtocol():
    try:
        from ovs.extensions.generic.configuration import Configuration

        if Configuration.get("/ovs/framework/rdma"):
            return "rdma"
        else:
            return "tcp"
    except:
        return "tcp"


def getLocalStorageRouter():
    localips = j.system.net.getIpAddresses()
    for storagerouter in StorageRouterList.get_storagerouters():
        if storagerouter.ip in localips:
            return storagerouter


def getEdgeconnection(vpoolname=VPOOLNAME):
    protocol = getEdgeProtocol()
    storagedrivers = list(StorageDriverList.get_storagedrivers())
    random.shuffle(storagedrivers)
    for storagedriver in storagedrivers:
        if storagedriver.status == "FAILURE":
            continue
        if (vpoolname is not None and storagedriver.vpool.name == vpoolname) or (
            vpoolname is None and storagedriver.vpool.name != VPOOLNAME
        ):
            return storagedriver.storage_ip, storagedriver.ports["edge"], protocol
    return None, None, protocol


def getVPoolByIPandPort(ip, port):
    for storagerouter in StorageRouterList.get_storagerouters():
        for storagedriver in storagerouter.storagedrivers:
            if storagedriver.ports["edge"] == port and storagedriver.storage_ip == ip:
                return storagedriver.vpool
    raise RuntimeError("Could not find vpool for {}:{}".format(ip, port))


def _getVPoolByUrl(url, vpoolname=None):
    if vpoolname is None and url.port:
        vpool = getVPoolByIPandPort(url.hostname, url.port)
    elif vpoolname is None:
        vpool = VPoolList.get_vpool_by_name(VPOOLNAME)
    else:
        vpool = VPoolList.get_vpool_by_name(vpoolname)
    return vpool


def getVDisk(path, vpool=None, timeout=None):
    url = urlparse.urlparse(path)
    if url.netloc == "":
        path = path.replace("{}:".format(url.scheme), "{}://".format(url.scheme))
        url = urlparse.urlparse(path)

    path = "/" + url.path.strip("/")
    path = path.split(":")[0]  # cause yeah putting nonestandard url params
    if not path.endswith(".raw"):
        path += ".raw"
    elif not url.scheme:
        parts = url.path.split("/")[1:]  # remove first slash
        if parts[0] == "mnt":
            vpool = parts[1]
            path = "/" + "/".join(parts[2:])

    vpool = _getVPoolByUrl(url, vpool)
    disk = VDiskList.get_by_devicename_and_vpool(path, vpool)
    if timeout is not None:
        start = time.time()
        while not disk and start + timeout > time.time():
            time.sleep(2)
            disk = VDiskList.get_by_devicename_and_vpool(path, vpool)
    return disk


def getUrlPath(path, vpoolname=VPOOLNAME):
    storageip, edgeport, protocol = getEdgeconnection(vpoolname)
    newpath, ext = os.path.splitext(path)
    if ext != ".raw":
        newpath = path
    newpath = newpath.strip("/")
    if newpath.startswith("mnt/"):
        newpath = "/".join(newpath.split("/")[2:])
    if not storageip:
        raise RuntimeError("Could not find edge connection")
    return "openvstorage+{protocol}://{ip}:{port}/{name}".format(
        protocol=protocol, ip=storageip, port=edgeport, name=newpath
    )


def getCredentials():
    if not CREDENTIALS:
        scl = j.clients.osis.getNamespace("system")
        grid = scl.grid.get(j.application.whoAmI.gid)
        settings = grid.settings.get("ovs_credentials", {})
        CREDENTIALS.extend([settings.get("edgeuser"), settings.get("edgepassword")])
    return CREDENTIALS


def getOpenvStorageURL(url):
    if url.startswith("openvstorage"):
        username, password = getCredentials()
        url = url.replace("://", ":")
        if username and password:
            url += ":username={}:password={}".format(username, password)
    return url


def getPath(path, vpoolname=None):
    """ Get path from referenceId of VM"""
    url = urlparse.urlparse(path)
    vpool = _getVPoolByUrl(url, vpoolname)
    path = url.path.strip("/")
    pathparts = path.split("/")
    if pathparts[0] == "mnt":
        path = "/".join(pathparts[2:])
    if not path.startswith("/mnt/%s" % vpool.name):
        path = os.path.join("/mnt/%s" % vpool.name, path)

    # Strip vdiskguid from path
    head, sep, tail = path.partition("@")
    path = head

    if not path.endswith(".raw"):
        path += ".raw"
    return path


def copyImage(srcpath):
    srcpath = getOpenvStorageURL(srcpath)
    imagename = os.path.splitext(j.system.fs.getBaseName(srcpath))[0]
    templatepath = "templates/%s.raw" % imagename
    dest = getOpenvStorageURL(getUrlPath("templates/%s" % imagename))
    if not getVDisk(templatepath):
        j.system.platform.qemu_img.convert(srcpath, None, dest, "raw")
        truncate(getPath(templatepath))
    diskguid = setAsTemplate(templatepath)
    return diskguid, dest


def importVolume(srcpath, destpath, data=False):
    srcpath = getOpenvStorageURL(srcpath)
    desturl = getOpenvStorageURL(destpath)
    ovsdest = getOpenvStorageURL(desturl)
    j.system.platform.qemu_img.convert(srcpath, None, ovsdest, "raw", createTarget=False)


def exportVolume(srcpath, destpath):
    srcpath = getOpenvStorageURL(srcpath)
    j.system.platform.qemu_img.convert(
        srcpath.replace("://", ":", 1), None, destpath, "vmdk"
    )
    return destpath


class Rawdevice(object):
    def __init__(self, url):
        self.url = getOpenvStorageURL(url)
        self.device = None
        if not j.system.fs.exists("/sys/module/nbd/"):
            j.system.process.execute("modprobe nbd")

    def __enter__(self):
        for nbddevice in glob("/dev/nbd*"):
            exitcode, _ = j.system.process.execute(
                "qemu-nbd -c {} -f raw {}".format(nbddevice, self.url),
                dieOnNonZeroExitCode=True,
            )
            if exitcode == 0:
                self.device = nbddevice
                return self
        raise RuntimeError("Could not find available nbd device")

    def __exit__(self, *args, **kwargs):
        if self.device:
            j.system.process.execute("qemu-nbd -d {}".format(self.device))


class TempStorage(object):

    BASE = "/mnt/%s/tmp" % VPOOLNAME

    def __init__(self):
        self.path = None
        self.raw = None

    def __enter__(self):
        j.system.fs.createDir(self.BASE)
        raw = tempfile.mktemp(".raw", dir=self.BASE)
        self.raw = raw
        truncate(raw, 2 * 1024 * 1024 * 1024 * 1024)
        proc = subprocess.Popen(
            ["mkfs.btrfs", raw], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            self.__exit__()
            raise RuntimeError(
                "Cannot make file system for the raw device: %s / %s" % (stdout, stderr)
            )
        path = j.system.fs.getTmpDirPath()
        self.path = path
        proc = subprocess.Popen(
            ["mount", "-t", "btrfs", "-o", "loop", self.raw, self.path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.communicate()
        if proc.returncode != 0:
            self.__exit__()
            raise RuntimeError("Cannot mount loop device")
        return self

    def __exit__(self, *args, **kwargs):
        if self.path is not None and os.path.exists(self.path):
            time.sleep(2)
            j.system.process.execute('umount "%s"' % self.path)
            j.system.fs.removeDirTree(self.path)
            getVDisk(self.path, timeout=10)
        if self.raw is not None and os.path.exists(self.raw):
            j.system.fs.remove(self.raw)


def truncate(filepath, size=None):
    if size is None:
        size = os.stat(filepath).st_size
    fd = os.open(filepath, os.O_RDWR | os.O_CREAT)
    try:
        os.ftruncate(fd, size)
    finally:
        os.close(fd)
