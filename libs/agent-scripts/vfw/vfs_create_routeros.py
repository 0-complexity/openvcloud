from JumpScale import j

descr = """
create and start a routeros image
"""

organization = "jumpscale"
author = "deboeckj@codescalers.com"
license = "bsd"
version = "1.0"
category = "deploy.routeros"
enable = True
async = True
queue = "default"
docleanup = True


def cleanup(name, networkid, bridge):
    import libvirt
    from CloudscalerLibcloud.utils.network import Network

    network = Network()
    con = network.libvirtutil.connection
    try:
        try:
            dom = con.lookupByName(name)
            network.cleanup_external(dom)
            network.cleanup_gwmgmt(dom)
            if dom.isActive():
                dom.destroy()
            dom.undefine()
        except libvirt.libvirtError:
            pass
        network.libvirtutil.cleanupNetwork(networkid, [bridge])
    finally:
        network.close()

    destinationfile = "/var/lib/libvirt/images/routeros/{:04x}/routeros.qcow2".format(
        networkid
    )
    if j.system.fs.exists(destinationfile):
        j.system.fs.remove(destinationfile)


def createVM(xml, netinfo):
    from CloudscalerLibcloud.utils.network import NetworkTool
    from CloudscalerLibcloud.utils import libvirtutil
    con = libvirtutil.LibvirtUtil()
    try:
        with NetworkTool(netinfo, con):
            # setup network vxlan
            print ("Creating network")
            dom = con.connection.defineXML(xml)
            dom.create()
            return dom.UUIDString()
    finally:
        con.close()


def action(vfw):
    from CloudscalerLibcloud.utils import libvirtutil
    from CloudscalerLibcloud.utils.network import Network, NetworkTool
    import pexpect
    import netaddr
    import jinja2
    import time
    import uuid
    import os

    hrd = j.atyourservice.get(name="vfwnode", instance="main").hrd
    networkid = vfw['id']
    publicnet = netaddr.IPNetwork(vfw['external']['ips'][0])
    publicip = str(publicnet.ip)
    publicgwip = vfw['external']['gateway']
    publiccidr = publicnet.prefixlen
    password = str(uuid.uuid4())
    privatenetwork = vfw['privatenetwork']
    vlan = vfw['external']['vlan']

    netrange = hrd.get("instance.vfw.netrange.internal")
    defaultpasswd = hrd.get("instance.vfw.admin.passwd")
    username = hrd.get("instance.vfw.admin.login")
    newpassword = hrd.get("instance.vfw.admin.newpasswd")
    bridgename = j.system.ovsnetconfig.getVlanBridge(vlan)
    destinationfile = None

    data = {
        "nid": j.application.whoAmI.nid,
        "gid": j.application.whoAmI.gid,
        "username": username,
        "password": newpassword,
    }

    networkidHex = "%04x" % int(networkid)
    internalip = str(
        netaddr.IPAddress(netaddr.IPNetwork(netrange).first + int(networkid))
    )
    privatenet = netaddr.IPNetwork(privatenetwork)
    name = "routeros_%s" % networkidHex

    j.clients.redisworker.execFunction(
        cleanup, _queue="hypervisor", name=name, networkid=networkid, bridge=bridgename
    )
    print "Testing network"
    if not j.system.net.tcpPortConnectionTest(internalip, 22, 1):
        print "OK no other router found."
    else:
        raise RuntimeError("IP conflict there is router with %s" % internalip)

    connection = libvirtutil.LibvirtUtil()
    network = Network(connection)
    netinfo = [{"type": "vlan", "id": vlan}, {"type": "vxlan", "id": networkid}]
    try:
        templatepath = "/var/lib/libvirt/images/routeros/template/routeros.qcow2"
        destination = "/var/lib/libvirt/images/routeros/%s/" % networkidHex
        destinationfile = os.path.join(destination, "routeros.qcow2")
        print "Creating image snapshot %s -> %s" % (templatepath, destination)
        if j.system.fs.exists(destinationfile):
            raise RuntimeError("Path %s already exists" % destination)
        j.system.fs.createDir(destination)
        j.system.fs.copyFile(templatepath, destinationfile)

        imagedir = j.system.fs.joinPaths(j.dirs.baseDir, "apps/routeros/template/")
        xmltemplate = jinja2.Template(
            j.system.fs.fileGetContents(
                j.system.fs.joinPaths(imagedir, "routeros-template.xml")
            )
        )
        xmlsource = xmltemplate.render(
            networkid=networkidHex,
            destinationfile=destinationfile,
            publicbridge=bridgename,
        )

        print "Starting VM"
        try:
            domuuid = j.clients.redisworker.execFunction(
                createVM, _queue="hypervisor", xml=xmlsource, netinfo=netinfo, _timeout=180
            )
        except Exception, e:
            raise RuntimeError(
                "Could not create VFW vm from template, network id:%s:%s\n%s"
                % (networkid, networkidHex, e)
            )
        print "Protect network"
        domain = connection.get_domain_obj(domuuid)
        network.protect_external(domain, publicip)
        network.protect_gwmgmt(domain, internalip)

        data["internalip"] = internalip
        run = pexpect.spawn("virsh console %s" % name, timeout=300)
        try:
            print "Waiting to attach to console"
            run.expect("Connected to domain", timeout=10)
            run.sendline()  # first enter to clear welcome message of kvm console
            print "Waiting for Login"
            run.expect("Login:", timeout=120)
            run.sendline(username)
            run.expect("Password:", timeout=10)
            run.sendline(defaultpasswd)
            print "waiting for prompt"
            run.expect("\] >", timeout=120)  # wait for primpt
            run.send("/ip addr add address=%s/22 interface=ether3\r\n" % internalip)
            print "waiting for end of command"
            run.expect("\] >", timeout=10)  # wait for primpt
            run.send("/quit\r\n")
            run.expect("Login:", timeout=10)
        except Exception, e:
            raise RuntimeError(
                "Could not set internal ip on VFW, network id:%s:%s\n%s"
                % (networkid, networkidHex, e)
            )
        finally:
            run.close()

        print "wait max 30 sec on tcp port 22 connection to '%s'" % internalip
        if j.system.net.waitConnectionTest(internalip, 80, timeout=30):
            print "Router is accessible, initial configuration probably ok."
        else:
            raise RuntimeError("Could not connect to router on %s" % internalip)

        ro = j.clients.routeros.get(internalip, username, defaultpasswd)
        ro.do("/system/identity/set", {"name": "%s/%s" % (networkid, networkidHex)})
        ro.do("/system/hardware/set", {"multi-cpu": "no"})
        ro.executeScript("/file remove numbers=[/file find]")
        ro.executeScript("/ip socks set enabled=no")

        # create certificates
        certdir = j.system.fs.getTmpDirPath()
        j.tools.sslSigning.create_self_signed_ca_cert(certdir)
        j.tools.sslSigning.createSignedCert(certdir, "server")

        ro.uploadFilesFromDir(certdir)
        vpnpassword = j.tools.hash.sha1(j.system.fs.joinPaths(certdir, "ca.crt"))
        j.system.fs.removeDirTree(certdir)

        if "skins" not in ro.list("/"):
            ro.mkdir("/skins")
        ro.uploadFilesFromDir("skins", "/skins")

        pubip = "%s/%s" % (publicip, publiccidr)
        ro.uploadExecuteScript(
            "basicnetwork",
            vars={
                "$pubip": pubip,
                "$privateip": str(privatenet.ip + 1),
                "$startpoolip": str(privatenet.ip + 2),
                "$endpoolip": str(privatenet.ip + 10),
                "$netmask": str(privatenet.netmask),
                "$prefix": str(privatenet.prefixlen),
                "$cidr": str(privatenet),
            },
        )
        ro.uploadExecuteScript("route", vars={"$gw": publicgwip})
        ro.uploadExecuteScript("certificates")
        ro.uploadExecuteScript(
            "ppp",
            vars={"$vpnpassword": vpnpassword, "$privateip": str(privatenet.ip + 1)},
        )
        ro.uploadExecuteScript("systemscripts")
        ro.uploadExecuteScript("services")

        # skin default
        ro.uploadExecuteScript("customer", vars={"$password": password})

        # dirty cludge: rebooting ROS here, as ftp service doesn't propagate directories
        try:
            ro.executeScript("/system reboot")
        finally:
            ro.close()

        # We're waiting for reboot
        start = time.time()
        timeout = 60
        while time.time() - start < timeout:
            try:
                ro = j.clients.routeros.get(internalip, username, defaultpasswd)
                try:
                    ro.executeScript(
                        "/user group set [find name=customer] skin=customer"
                    )
                finally:
                    ro.close()
                break
            except Exception as e:
                print "Failed to set skin will try again in 1sec", e
            time.sleep(1)
        else:
            raise RuntimeError("Failed to set customer skin")

        for x in xrange(30):
            ro = j.clients.routeros.get(internalip, username, defaultpasswd)
            try:
                if ro.arping(publicgwip, "public"):
                    break
            finally:
                ro.close()
            time.sleep(1)
        else:
            raise RuntimeError(
                "Could not ping to:%s for VFW %s" % (publicgwip, networkid)
            )

        # now, set the pasword
        try:
            ro = j.clients.routeros.get(internalip, username, defaultpasswd)
            try:
                ro.executeScript("/user set %s password=%s" % (username, newpassword))
            finally:
                ro.close()
        except:
            pass

        print "Finished configuring VFW"

    except:
        if docleanup:
            j.clients.redisworker.execFunction(
                cleanup, _queue="hypervisor", name=name, networkid=networkid, bridge=bridgename
            )
        raise
    finally:
        network.close()

    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--networkid", type=int, required=True)
    parser.add_argument("-p", "--public-ip", dest="publicip", required=True)
    parser.add_argument(
        "-pn", "--private-net", dest="privatenet", default="192.168.104.0/24"
    )
    parser.add_argument("-pg", "--public-gw", dest="publicgw", required=True)
    parser.add_argument(
        "-pc", "--public-cidr", dest="publiccidr", required=True, type=int
    )
    parser.add_argument("-v", "--vlan", dest="vlan", required=True, type=int)
    parser.add_argument("-pw", "--password", default="rooter")
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        default=False,
        help="Cleanup in case of failure",
    )
    options = parser.parse_args()
    docleanup = options.cleanup
    action(
        options.networkid,
        options.publicip,
        options.publicgw,
        options.publiccidr,
        options.password,
        options.vlan,
        options.privatenet,
    )
