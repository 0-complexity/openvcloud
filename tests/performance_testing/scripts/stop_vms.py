#!/usr/bin/python3
from gevent import monkey

monkey.patch_all()
from optparse import OptionParser
from libtest import execute_async_ovc
import gevent
import signal
from ovc_client import Client


def main(options):

    ovc = Client(options.environment, options.application_id, options.secret)

    def hardshutdown_vm(machine_id):
        def _run(job):
            job = execute_async_ovc(
                ovc, "cloudapi/machines/stop", machineId=machine_id, force=True
            )
            job.link_value(lambda _: print("Succesfully killed vm %s" % machine_id))
            job.link_exception(lambda _: print("Failed to stop vm %s" % machine_id))

        return _run

    def print_message(message):
        def _run(_):
            print(message)

        return _run

    def shutdown_vms(job):
        machines = job.get()
        for machine in machines:
            machine_id = machine["id"]
            if machine["status"] != "RUNNING":
                print(
                    "Skipping machine {} with status {}".format(
                        machine_id, machine["status"]
                    )
                )
                continue
            job = execute_async_ovc(ovc, "cloudapi/machines/stop", machineId=machine_id)
            job.link_value(print_message("Succesfully shutdown vm %s" % machine_id))
            job.link_exception(hardshutdown_vm(machine_id))

    def shutdown_cloudspaces(job):
        for cloudspace in job.get():
            cloudspace_id = cloudspace["id"]
            print(
                "Listing machines in cloudspace {} (id={}, status={})".format(
                    cloudspace["name"], cloudspace_id, cloudspace["status"]
                )
            )
            job = execute_async_ovc(
                ovc, "cloudapi/machines/list", cloudspaceId=cloudspace_id
            )
            job.link(shutdown_vms)
            job.link_exception(print_message)

    job = execute_async_ovc(ovc, "cloudapi/cloudspaces/list")
    job.link(shutdown_cloudspaces)
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
        "-e",
        "--env",
        dest="environment",
        type="string",
        help="environment utl to login on the OVC api",
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
        gevent.signal(signal.SIGQUIT, gevent.kill)
        main(options)
