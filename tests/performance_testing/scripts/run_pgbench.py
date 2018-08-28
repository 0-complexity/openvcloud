#!/usr/bin/python3
import signal
from argparse import ArgumentParser
import os
import datetime
import gevent
import csv
from gevent.lock import BoundedSemaphore
from gevent import monkey

monkey.patch_all()
from libtest import run_cmd_via_gevent  # noqa: E402
from libtest import check_package, push_results_to_repo  # noqa: E402
from libtest import prepare_test  # noqa: E402
from ovc_client import Client


machines_running = set()
machines_complete = set()


def pgbench(options, machine_id, publicip, publicport, account):
    machines_running.add(machine_id)
    # only one data disk for this test
    templ = 'sshpass -p "{}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {} {}@{} '
    templ += " bash run_pgbench.sh {} {} {} {} {} {}"
    cmd = templ.format(
        account["password"],
        publicport,
        account["login"],
        publicip,
        account["password"],
        "vdb",
        options.scalefactor,
        options.testrun_time,
        options.threadcount,
        options.clientcount,
    )
    print(
        "Postgress benchmarking testing has been started on machine: {}".format(
            machine_id
        )
    )
    iops = int(run_cmd_via_gevent(cmd).splitlines()[-1])
    machines_complete.add(machine_id)
    running = machines_running.difference(machines_complete)
    complete = (len(machines_running) - len(running)) / len(machines_running) * 100.0
    print(
        "Machine {} reports {} iops. Testing completed for {:.2f}%".format(
            machine_id, iops, complete
        )
    )

    return machine_id, iops


def main(options):

    # Check dependencies
    if not os.path.exists(options.results_dir):
        print("Not all dependencies are met. Make sure the result directory exists.")
        return

    if not check_package("sshpass") or not check_package("python3-prettytable"):
        return

    # Prepare test run
    hostname = run_cmd_via_gevent("hostname").replace("\n", "")
    test_num = len(os.listdir("{}".format(options.results_dir))) + 1
    test_dir = "/" + datetime.datetime.today().strftime("%Y-%m-%d")
    test_dir += "_" + hostname + "_pgbench_testresults_{}".format(test_num)
    results_dir = options.results_dir + test_dir
    run_cmd_via_gevent("mkdir -p {}".format(results_dir))

    # list virtual and deployed cloudspaces
    vms = []
    vms_index = set()
    ovc = Client(options.environment, options.application_id, options.secret)
    cloudspaces_per_user = ovc.request("cloudapi/cloudspaces/list")
    for cs in cloudspaces_per_user:
        if cs["name"] == "template_space":
            continue
        portforwards = ovc.request(
            "cloudapi/portforwarding/list", cloudspaceId=cs["id"]
        )
        for pi in portforwards:
            if "machineId" not in pi or pi["machineId"] in vms_index:
                continue
            vms.append([pi["machineId"], pi["publicIp"], pi["publicPort"]])
            vms_index.add(pi["machineId"])

    if len(vms) < options.required_vms:
        print(
            "Not enough vms available to run this test. {} < {}".format(
                len(vms), options.required_vms
            )
        )
        return
    vms = vms[: options.required_vms]

    # prepare test
    files = ["{}/4_pgbench/run_pgbench.sh".format(options.testsuite)]
    pjobs = [
        gevent.spawn(prepare_test, ovc, concurrency, options, files, *vm) for vm in vms
    ]
    gevent.joinall(pjobs)

    # run pgbench tests
    rjobs = [
        gevent.spawn(pgbench, options, *job.value)
        for job in pjobs
        if job.value is not None
    ]
    gevent.joinall(rjobs)

    # report results
    with open(os.path.join(results_dir, "parameters.md"), "w") as params:
        params.write("# Parameters\n\n")
        for key, value in vars(options).items():
            params.write("- **{}**: {}\n".format(key, value))
    total_iops = 0
    with open(os.path.join(results_dir, "results.csv"), "w") as csvfile:
        fieldnames = ["machine_id", "iops"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for job in rjobs:
            machine_id, iops = job.value
            if iops == 0:
                continue  # skip machines whith errors
            writer.writerow({"machine_id": machine_id, "iops": iops})
            total_iops += iops
        writer.writerow({"machine_id": "total iops", "iops": total_iops})
    print("==========================")
    print("Total iops: {}".format(total_iops))
    print("==========================")

    # pushing results to env_repo
    push_results_to_repo(results_dir, options.environment)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-u",
        "--user",
        dest="username",
        required=True,
        help="username to login on the OVC api",
    )
    parser.add_argument(
        "-e",
        "--env",
        dest="environment",
        required=True,
        help="environment url to login on the OVC api",
    )
    parser.add_argument(
        "-t",
        "--run_time",
        dest="testrun_time",
        type=int,
        default=300,
        help=" Test-rum time per virtual machine  (in seconds)",
    )
    parser.add_argument(
        "-v",
        "--vms",
        dest="required_vms",
        type=int,
        default=2,
        help=" selected number of virtual machines to run fio on",
    )
    parser.add_argument(
        "-r",
        "--rdir",
        dest="results_dir",
        default="/root/G8_testing/tests_results/pgbench",
        help="absolute path fot results directory",
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
        "-s",
        "--ts",
        dest="testsuite",
        default="../Testsuite",
        help="location to find Testsuite directory",
    )
    parser.add_argument(
        "-f",
        "--sf",
        dest="scalefactor",
        default="100",
        help="100 create 10mio records in test db",
    )
    parser.add_argument(
        "-c",
        "--tc",
        dest="threadcount",
        default="2",
        help="number of threads that run the test simultaniously",
    )
    parser.add_argument(
        "-l",
        "--cc",
        dest="clientcount",
        default="10",
        help="number of client connections to the database",
    )
    parser.add_argument(
        "-appid",
        "--application_id",
        dest="application_id",
        help="itsyouonline Application Id",
    )
    parser.add_argument(
        "-secret", "--secret", dest="secret", help="itsyouonline Secret"
    )

    options = parser.parse_args()
    gevent.signal(signal.SIGQUIT, gevent.kill)
    concurrency = BoundedSemaphore(options.concurrency)
    main(options)
