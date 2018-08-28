#!/usr/bin/python3
from gevent import monkey

monkey.patch_all()
from gevent.lock import BoundedSemaphore
from optparse import OptionParser
from libtest import execute_async_ovc
import gevent
import signal
from ovc_client import Client


def main(options):
    ovc = Client(options.environment, options.application_id, options.secret)

    def print_message(message):
        def _run(_):
            print(message)

        return _run

    def start_vms(job):
        for machine in job.get():
            if machine["status"] != "HALTED":
                continue
            machine_id = machine["id"]
            # Need to start machines one by one, to work arround OVC problem.
            # Otherwise they get started all on the same node
            with concurrency:
                try:
                    ovc.request("cloudapi/machines/start")(machineId=machine_id)
                    print("Succesfully started vm %s" % machine_id)
                except:
                    print("Could not start vm %s" % machine_id)
            # job = execute_async_ovc(ovc, ovc.api.cloudapi.machines.start, machineId=machine_id)
            # job.link_value(print_message("Succesfully started vm %s" % machine_id))
            # job.link_exception(print_message("Could not start vm %s" % machine_id))

    def start_cloudspaces(job):
        for cloudspace in job.get():
            cloudspace_id = cloudspace["id"]
            job = execute_async_ovc(
                ovc, "cloudapi/machines/list", cloudspaceId=cloudspace_id
            )
            job.link(start_vms)

    job = execute_async_ovc(ovc, "cloudapi/cloudspaces/list")
    job.link(start_cloudspaces)
    gevent.wait()


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
        "--env",
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
