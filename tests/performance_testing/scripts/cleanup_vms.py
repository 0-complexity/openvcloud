#!/usr/bin/python3
from gevent import monkey

monkey.patch_all()
from optparse import OptionParser  # noqa: E402
import gevent  # noqa: E402
import signal  # noqa: E402
import time  # noqa: E402
import os  # noqa: E402
from ovc_client import Client
from gevent.lock import BoundedSemaphore  # noqa: E402


def delete_vm(ovc, machine_id):
    with concurrency:
        print("Deleting machine {}".format(machine_id))
        ovc.request("cloudapi/machines/delete", machineId=machine_id)


def delete_cs(ovc, cloudspace_id):
    with concurrency:
        print("Deleting cloudspace {}".format(cloudspace_id))
        ovc.request("cloudapi/cloudspaces/delete", cloudspaceId=cloudspace_id)


def main(options):
    ovc = Client(options.environment, options.application_id, options.secret)
    while True:
        cloudspaces = ovc.request("cloudapi/cloudspaces/list")
        if not cloudspaces:
            break
        jobs = list()
        for cloudspace in cloudspaces:
            cloudspace_id = cloudspace["id"]
            vms = ovc.request("cloudapi/machines/list", cloudspaceId=cloudspace_id)
            jobs.extend(
                [
                    gevent.spawn(delete_vm, ovc, vm["id"])
                    for vm in vms
                    if vm["name"] != "template_vm"
                ]
            )
        gevent.joinall(jobs)
        jobs = list()
        for cloudspace in cloudspaces:
            cloudspace_id = cloudspace["id"]
            vms = ovc.request("cloudapi/machines/list", cloudspaceId=cloudspace_id)
            jobs.extend([gevent.spawn(delete_vm, ovc, vm["id"]) for vm in vms])
        gevent.joinall(jobs)
        jobs = list()
        for cloudspace in cloudspaces:
            cloudspace_id = cloudspace["id"]
            vms = ovc.request("cloudapi/machines/list", cloudspaceId=cloudspace_id)
            if not vms:
                jobs.append(gevent.spawn(delete_cs, ovc, cloudspace_id))
        gevent.joinall(jobs)


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option(
        "-u",
        "--user",
        dest="username",
        type="string",
        help="username to login on the OVC api",
    )
    parser.add_option(
        "-p",
        "--pwd",
        dest="password",
        type="string",
        help="password to login on the OVC api",
    )
    parser.add_option(
        "-e",
        "--environment",
        dest="environment",
        type="string",
        help="environment url to login on the OVC api",
    )
    parser.add_option(
        "-n",
        "--con",
        dest="concurrency",
        default=2,
        type="int",
        help="amount of concurrency to execute the job",
    )
    parser.add_option(
        "-a",
        "--application_id",
        dest="application_id",
        help="itsyouonline Application Id",
    )
    parser.add_option("-s", "--secret", dest="secret", help="itsyouonline Secret")

    (options, args) = parser.parse_args()
    if not options.username or not options.environment:
        parser.print_usage()
    else:
        concurrency = BoundedSemaphore(options.concurrency)
        gevent.signal(signal.SIGQUIT, gevent.kill)
        main(options)
