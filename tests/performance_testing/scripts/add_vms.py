#!/usr/bin/python3
from gevent import monkey

monkey.patch_all()
import gevent
import signal
import time
import os
import sys
from ovc_client import Client
from libtest import (
    run_cmd_via_gevent,
    wait_until_remote_is_listening,
    safe_get_vm,
    get_logger,
)
from argparse import ArgumentParser
from gevent.lock import BoundedSemaphore

_cloudspace_semaphores = dict()
_stats = dict(deployed_vms=0, deployed_cloudspaces=0)
_vmnamecache = dict()

TEMPLATE_NAME = "performance_testing"

logger = get_logger("add_vms")


def get_publicport_semaphore(cloudspace_id):
    if cloudspace_id not in _cloudspace_semaphores:
        _cloudspace_semaphores[cloudspace_id] = BoundedSemaphore()
    return _cloudspace_semaphores[cloudspace_id]


def get_vm_name(cloudspace_id, counter):
    return "vm-{0}-{1:0>3}".format(cloudspace_id, counter)


class Deployer(object):
    def __init__(self, options):
        self.options = options
        self.ovc = Client(options.environment, options.application_id, options.secret)

        # Get account id
        print("Getting account id")
        tmp = self.ovc.request("cloudapi/accounts/list")
        if len(tmp) != 1:
            print(
                "FAILURE: Expected to only find 1 account and found {}".format(len(tmp))
            )
            return
        self.account_id = tmp[0]["id"]

        # Get location gid
        print("Getting location gid")
        self.gid = next(
            (
                loc["gid"]
                for loc in self.ovc.request("cloudapi/locations/list")
                if loc["locationCode"] == options.location
            ),
            None,
        )
        if self.gid is None:
            print("FAILURE: Could not determine gid")
            sys.exit(1)

    def create_performance_test_image(self):
        image_id = next(
            (
                img["id"]
                for img in self.ovc.request(
                    "cloudapi/images/list", accountId=self.account_id
                )
                if img["name"] == TEMPLATE_NAME
            ),
            None,
        )
        if image_id:
            print("Found template for performance_testing")
            return image_id
        print("Checking if source image is available")
        image_id = next(
            (
                img["id"]
                for img in self.ovc.request("cloudapi/images/list")
                if img["name"] == options.image
            ),
            None,
        )
        if image_id is None:
            print("FAILURE: Could not find image.")
            sys.exit(1)

        print("Getting template_space")
        cloudspace_id = next(
            (
                space["id"]
                for space in self.ovc.request("cloudapi/cloudspaces/list")
                if space["name"] == "template_space"
            ),
            None,
        )
        if cloudspace_id is None:
            print("Creating template_space")
            cloudspace_id = self.deploy_cloudspace("template_space")

        size_id = self.get_size_id(cloudspace_id)

        print("Getting template_vm")
        machine_id = next(
            (
                machine["id"]
                for machine in self.ovc.request(
                    "cloudapi/machines/list", cloudspaceId=cloudspace_id
                )
                if machine["name"] == "template_vm"
            ),
            None,
        )
        if machine_id is None:
            print("Getting template_vm")
            machine = self.safe_deploy_vm(
                "template_vm", cloudspace_id, image_id, size_id=size_id
            )
            machine_id = machine["id"]
            cloudspace = self.ovc.request(
                "cloudapi/cloudspaces/get", cloudspaceId=cloudspace_id
            )
            print("Installing requirements")
            while True:
                try:
                    self.install_req(machine, cloudspace)
                    break
                except:
                    print("Retrying ...")
                    gevent.sleep(5)
            print("Remove portforwarding from templatevm")
            self.ovc.request(
                "cloudapi/portforwarding/deleteByPort",
                cloudspaceId=cloudspace_id,
                publicIp=cloudspace["externalnetworkip"],
                publicPort=machine["public_port"],
                proto="tcp",
            )
            print("Stopping template vm")
            self.ovc.request("cloudapi/machines/stop", machineId=machine_id)
            print("Creating snapshot")
            self.ovc.request(
                "cloudapi/machines/snapshot", machineId=machine_id, name=TEMPLATE_NAME
            )
        print("Getting snapshot")
        snapshot_timestamp = next(
            (
                snapshot["epoch"]
                for snapshot in self.ovc.request(
                    "cloudapi/machines/listSnapshots", machineId=machine_id
                )
                if snapshot["name"] == TEMPLATE_NAME
            ),
            None,
        )
        if snapshot_timestamp is None:
            print("FAILURE: Found template vm without template snapshot")
            sys.exit(1)
        return machine_id, snapshot_timestamp

    def get_size_id(self, cloudspace_id):
        sizes = self.ovc.request("cloudapi/sizes/list", cloudspaceId=cloudspace_id)
        size_id = next(
            (
                s["id"]
                for s in sizes
                if (
                    self.options.bootdisk in s["disks"]
                    and self.options.memory == s["memory"]
                    and self.options.cpu == s["vcpus"]
                )
            ),
            None,
        )
        if size_id is None:
            raise ValueError("Could not find size_id matching VM specifications")
        return size_id

    def install_req(self, machine, cloudspace):
        account = machine["accounts"][0]

        # Wait until vm accepts connections
        wait_until_remote_is_listening(
            cloudspace["publicipaddress"], machine["public_port"]
        )

        # Copy install_deps.sh to vm
        templ = 'sshpass -p "{0}" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
        templ += " -P {1} install_deps.sh {2}@{3}:/home/{2}"
        cmd = templ.format(
            account["password"],
            machine["public_port"],
            account["login"],
            cloudspace["externalnetworkip"],
        )
        run_cmd_via_gevent(cmd)

        # Run bash script on vm
        templ = 'sshpass -p "{0}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {1} {2}@{3} '
        templ += "'echo \"{0}\" | sudo -S bash /home/{2}/install_deps.sh'"
        cmd = templ.format(
            account["password"],
            machine["public_port"],
            account["login"],
            cloudspace["externalnetworkip"],
        )
        run_cmd_via_gevent(cmd)

    def safe_deploy_vm(
        self,
        name,
        cloudspace_id,
        template_details,
        datadisk=None,
        iops=None,
        size_id=None,
    ):
        while True:
            try:
                return self.deploy_vm(
                    name, cloudspace_id, template_details, datadisk, iops, size_id
                )
            except Exception as e:
                templ = "Failed creating machine {} in cloudspace {}, \nError: {}\nretrying ..."
                logger.error(templ.format(name, cloudspace_id, str(e)))
                gevent.sleep(10)
                while True:
                    try:
                        machines = self.ovc.request(
                            "cloudapi/machines/list", cloudspaceId=cloudspace_id
                        )
                        machine_id = next(
                            (m["id"] for m in machines if m["name"] == name), None
                        )
                        if machine_id is None:
                            break
                        self.ovc.request(
                            "cloudapi/machines/delete", machineId=machine_id
                        )
                        break
                    except Exception as e:
                        templ = "Failed cleaning up machine {} in cloudspace {}, \nError: {}\nretrying ..."
                        logger.error(templ.format(name, cloudspace_id, str(e)))
                        gevent.sleep(10)

    def deploy_vm(
        self,
        name,
        cloudspace_id,
        template_details,
        datadisk=None,
        iops=None,
        size_id=None,
    ):
        # Listing sizes
        if size_id is None:
            raise ValueError("No matching size for vm found.")

        if options.iops < 0:
            raise ValueError("Maximum iops can't be a negative value")

        # Create vm
        with concurrency:
            datadisks = [int(datadisk)] if datadisk else []
            if not isinstance(template_details, tuple):
                print("Creating {}".format(name))
                vm_id = self.ovc.request(
                    "cloudapi/machines/create",
                    cloudspaceId=cloudspace_id,
                    name=name,
                    description=name,
                    sizeId=size_id,
                    imageId=template_details,
                    disksize=options.bootdisk,
                    datadisks=datadisks,
                )
                limitIOdone = False
            else:
                print("Cloning {}".format(name))
                machine_id, snapshot_timestamp = template_details
                vm_id = self.ovc.request(
                    "cloudapi/machines/clone",
                    machineId=machine_id,
                    name=name,
                    cloudspaceId=cloudspace_id,
                    snapshotTimestamp=snapshot_timestamp,
                )
                print("Adding data disk to {}".format(name))
                disk_id = self.ovc.request(
                    "cloudapi/machines/addDisk",
                    machineId=vm_id,
                    diskName="data",
                    description="workhorse",
                    size=int(datadisk),
                    type="D",
                )
                if iops is not None:
                    print(
                        "Set limit of iops to {} on disk {}({}) for machine {}".format(
                            options.iops, "data", disk_id, name
                        )
                    )
                    self.ovc.request(
                        "cloudapi/disks/limitIO", diskId=disk_id, iops=iops
                    )
                    limitIOdone = True

        # limit the IOPS on all the disks of the vm
        machine = safe_get_vm(self.ovc, concurrency, vm_id)
        if iops is not None and not limitIOdone:
            for disk in machine["disks"]:
                if disk["type"] != "D":
                    continue
                with concurrency:
                    print(
                        "Set limit of iops to {} on disk {}({}) for machine {}".format(
                            options.iops, disk["name"], disk["id"], name
                        )
                    )
                    self.ovc.request(
                        "cloudapi/disks/limitIO", diskId=disk["id"], iops=iops
                    )

        # Wait until vm has ip address
        start = time.time()
        while True:
            gevent.sleep(5)
            machine = safe_get_vm(self.ovc, concurrency, vm_id)
            ip = machine["interfaces"][0]["ipAddress"]
            if ip != "Undefined":
                break
            now = time.time()
            if now > start + 600:
                raise RuntimeError(
                    "Machine {} did not get an ip within 600 seconds".format(vm_id)
                )
            print(
                "Waiting {} seconds for an IP for VM {}".format(int(now - start), name)
            )

        # Configure portforward to ssh port of vm
        print("Configuring portforward for machine {}".format(name))
        cloudspace = self.ovc.request(
            "cloudapi/cloudspaces/get", cloudspaceId=cloudspace_id
        )
        with get_publicport_semaphore(cloudspace_id):
            public_ports = [
                int(pf["publicPort"])
                for pf in self.ovc.request(
                    "cloudapi/portforwarding/list", cloudspaceId=cloudspace_id
                )
            ]
            public_ports.append(19999)
            public_port = max(public_ports) + 1
            with concurrency:
                self.ovc.request(
                    "cloudapi/portforwarding/create",
                    cloudspaceId=cloudspace_id,
                    publicIp=cloudspace["publicipaddress"],
                    publicPort=public_port,
                    machineId=vm_id,
                    localPort=22,
                    protocol="tcp",
                )
        machine["public_port"] = public_port
        print("Machine {} deployed succesfully.".format(name))
        _stats["deployed_vms"] += 1
        return machine

    def deploy_cloudspace(self, name):
        # Create cloudspace
        with concurrency:
            print("Creating cloudspace {}".format(name))
            cloudspace_id = self.ovc.request(
                "cloudapi/cloudspaces/create",
                accountId=self.account_id,
                location=options.location,
                name=name,
                access=options.username,
            )
            print("Checking if cloudspace {} is deployed".format(name))
            while True:
                cs = self.ovc.request(
                    "cloudapi/cloudspaces/get", cloudspaceId=cloudspace_id
                )
                if cs["status"] == "DEPLOYED":
                    break
                print("Waiting for cloudspace {} to be deployed".format(name))
                time.sleep(15)
            _stats["deployed_cloudspaces"] += 1
            return cloudspace_id


def main(options):
    # Check dependencies
    if not (os.path.exists("install_deps.sh") and os.path.exists("/usr/bin/sshpass")):
        print(
            "Not all dependencies are met. Make sure the install_deps.sh script"
            + " is in the current directory and sshpass is installed."
        )
        return
    deployer = Deployer(options)
    # Can we find the image we need ?
    template_details = deployer.create_performance_test_image()

    jobs = list()
    print("Checking if we need more cloudspaces")
    cloudspaces = list(
        filter(
            lambda space: space["name"].startswith("space-"),
            deployer.ovc.request("cloudapi/cloudspaces/list"),
        )
    )
    if len(cloudspaces) < options.cloudspaces:
        jobs.extend(
            [
                gevent.spawn(deployer.deploy_cloudspace, "space-{0:0>3}".format(x))
                for x in range(len(cloudspaces) + 1, int(options.cloudspaces) + 1)
            ]
        )

    gevent.joinall(jobs)
    jobs = list()
    # Add vms in existing cloudspaces
    cloudspaces = list(
        filter(
            lambda space: space["name"].startswith("space-"),
            deployer.ovc.request("cloudapi/cloudspaces/list"),
        )
    )
    print("Checking if we need more vms in existing cloudspaces")
    for cloudspace in cloudspaces:
        cloudspace_id = cloudspace["id"]
        expected_vms = [
            get_vm_name(cloudspace_id, x) for x in range(1, options.vmachines + 1)
        ]
        for vm in deployer.ovc.request(
            "cloudapi/machines/list", cloudspaceId=cloudspace_id
        ):
            if vm["name"] in expected_vms:
                expected_vms.remove(vm["name"])
        size_id = deployer.get_size_id(cloudspace_id)
        jobs.extend(
            [
                gevent.spawn(
                    deployer.safe_deploy_vm,
                    vm_name,
                    cloudspace_id,
                    template_details,
                    options.datadisk,
                    options.iops,
                    size_id,
                )
                for vm_name in expected_vms
            ]
        )
    gevent.joinall(jobs)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-u",
        "--user",
        dest="username",
        help="username to login on the OVC api",
        required=True,
    )
    parser.add_argument(
        "-p",
        "--pwd",
        dest="password",
        help="password to login on the OVC api",
        required=True,
    )
    parser.add_argument(
        "-e",
        "--environment",
        dest="environment",
        help="environment url to login on the OVC api",
        required=True,
    )
    parser.add_argument(
        "-l", "--loc", dest="location", help="location to create cloudspaces"
    )
    parser.add_argument(
        "-c",
        "--clspcs",
        dest="cloudspaces",
        type=int,
        default=5,
        help="minimum number of cloudspaces",
    )
    parser.add_argument(
        "-v",
        "--vms",
        dest="vmachines",
        type=int,
        default=5,
        help="minimum number of vmachines per cloudspace",
    )
    parser.add_argument(
        "-i",
        "--img",
        dest="image",
        default="Ubuntu 16.04 x64",
        help="image to use for creating vmachines",
    )
    parser.add_argument(
        "-b", "--boot", dest="bootdisk", type=int, help="bootdisk size", default=10
    )
    parser.add_argument(
        "-d", "--data", dest="datadisk", type=int, help="datadisk size", default=20
    )
    parser.add_argument(
        "-m",
        "--mem",
        dest="memory",
        default=1024,
        type=int,
        help="amount of memory for the virtual machines",
    )
    parser.add_argument(
        "-k",
        "--cpu",
        dest="cpu",
        default=1,
        type=int,
        help="amount of vcpus for the virtual machines",
    )
    parser.add_argument(
        "-o",
        "--iops",
        dest="iops",
        default=600,
        type=int,
        help="maximum of iops of the disks for the virtual machines",
    )
    parser.add_argument(
        "-n",
        "--con",
        dest="concurrency",
        default=2,
        type=int,
        help="amount of concurrency to execute the job",
    )
    parser.add_argument(
        "-a",
        "--application_id",
        dest="application_id",
        help="itsyouonline Application Id",
    )
    parser.add_argument("-s", "--secret", dest="secret", help="itsyouonline Secret")

    options = parser.parse_args()
    concurrency = BoundedSemaphore(options.concurrency)
    gevent.signal(signal.SIGQUIT, gevent.kill)
    start = time.time()
    main(options)
    end = time.time()
    elapsed = int(end - start)
    minutes = int(elapsed / 60)
    seconds = elapsed % 60
    tmpl = "Deployed {} cloudspace(s) and {} machine(s) in {} minutes and {} seconds"
    print(
        tmpl.format(
            _stats["deployed_cloudspaces"], _stats["deployed_vms"], minutes, seconds
        )
    )
