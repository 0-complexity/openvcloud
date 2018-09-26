#!/usr/bin/python3
import signal
from argparse import ArgumentParser
import os
import datetime
import gevent
import subprocess
from gevent.lock import BoundedSemaphore
from gevent import monkey

monkey.patch_all()
from libtest import run_cmd_via_gevent  # noqa: E402
from libtest import check_package, push_results_to_repo  # noqa: E402
from libtest import mount_disks, prepare_test  # noqa: E402
from ovc_client import Client


machines_running = set()
machines_complete = set()


def fio_test(options, machine_id, publicip, publicport, account):
    machines_running.add(machine_id)
    # only one data disk for this test
    disks_num = 1
    templ = 'sshpass -p "{}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {} {}@{} '
    templ += " python3 Machine_script.py {} {} {} {} {} {} {} {} {} {} {} {} {} {}"
    cmd = templ.format(
        account["password"],
        publicport,
        account["login"],
        publicip,
        options.testrun_time,
        machine_id,
        account["password"],
        1,
        disks_num,
        options.data_size,
        options.write_type,
        options.block_size,
        options.iodepth,
        options.direct_io,
        options.rwmixwrite,
        options.rate_iops,
        options.numjobs,
        options.type,
    )
    print("FIO testing has been started on machine: {}".format(machine_id))
    run_cmd_via_gevent(cmd)
    machines_complete.add(machine_id)
    running = machines_running.difference(machines_complete)
    complete = (len(machines_running) - len(running)) / len(machines_running) * 100.0
    print("Testing completed for {:.2f}%".format(complete))
    if complete >= 90.0:
        print(
            "Waiting for machines {} to complete their test ...".format(
                " ".join(str(x) for x in running)
            )
        )

    return account, publicport, publicip, machine_id


def assemble_fio_test_results(
    results_dir, account, publicport, cloudspace_publicip, machine_id
):
    print("Collecting results from machine: {}".format(machine_id))
    templ = "sshpass -p{} scp -r -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
    templ += "-P {}  {}@{}:machine{}_iter{}_{}_results {}/"
    cmd = templ.format(
        account["password"],
        publicport,
        account["login"],
        cloudspace_publicip,
        machine_id,
        1,
        options.write_type,
        results_dir,
    )
    run_cmd_via_gevent(cmd)


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
    test_dir += "_" + hostname + "_fio_testresults_{}".format(test_num)
    results_dir = options.results_dir + test_dir
    run_cmd_via_gevent("mkdir -p {}".format(results_dir))

    # list virtual and deployed cloudspaces
    vms = []
    vms_index = set()
    ovc = Client(options.environment, options.application_id, options.secret)
    cloudspaces_per_user = ovc.request("cloudapi/cloudspaces/list")
    cloudspaces_ids = options.cloudspaces
    if cloudspaces_ids:
        cloudspaces_ids = [int(_id) for _id in cloudspaces_ids.split(",")]
        cloudspaces_per_user = [
            cs for cs in cloudspaces_per_user if cs["id"] in cloudspaces_ids
        ]

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
    files = [
        "{}/1_fio_vms/Machine_script.py".format(options.testsuite),
        "{}/1_fio_vms/mount_disks.sh".format(options.testsuite),
    ]
    pjobs = [
        gevent.spawn(prepare_test, ovc, concurrency, options, files, *vm) for vm in vms
    ]
    gevent.joinall(pjobs)

    # mount disks if the filesystem will be used
    if options.type == "filesystem":
        gevent.joinall([gevent.spawn(mount_disks, ovc, concurrency, options, *vm) for vm in vms])

    # run fio tests
    rjobs = [
        gevent.spawn(fio_test, options, *job.value)
        for job in pjobs
        if job.value is not None
    ]
    gevent.joinall(rjobs)

    # collect results from machines
    rjobs = [
        gevent.spawn(assemble_fio_test_results, results_dir, *job.value)
        for job in rjobs
        if job.value is not None
    ]
    gevent.joinall(rjobs)

    # collecting results in csv file
    with open(os.path.join(results_dir, "parameters.md"), "w") as params:
        params.write("# Parameters\n\n")
        for key, value in vars(options).items():
            params.write("- **{}**: {}\n".format(key, value))
    cwd = os.getcwd()
    subprocess.run(
        ["cp", "{}/1_fio_vms/collect_results.py".format(options.testsuite), results_dir]
    )
    os.chdir(results_dir)
    subprocess.run(
        [
            "python3",
            "collect_results.py",
            "-dir",
            results_dir,
            "-env",
            options.environment,
            "-u",
            options.username,
            "-appid",
            options.application_id,
            "-secret",
            options.secret,
        ]
    )

    # pushing results to env_repo
    os.chdir(cwd)
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
    # parser.add_argument("-p", "--pwd", dest="password", required=True,
    #                     help="password to login on the OVC api")
    parser.add_argument(
        "-e",
        "--environment",
        dest="environment",
        required=True,
        help="environment url to login on the OVC api",
    )
    parser.add_argument(
        "-d",
        "--ds",
        dest="data_size",
        type=int,
        default=1000,
        help="Amount of data to be written per each data disk per VM (in MB)",
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
        "-w",
        "--IO_type",
        dest="write_type",
        default="randrw",
        help="Type of I/O pattern",
    )
    parser.add_argument(
        "-m",
        "--mixwrite",
        dest="rwmixwrite",
        type=int,
        default=20,
        help=" Percentage of a mixed workload that should be writes",
    )
    parser.add_argument(
        "-b", "--bs", dest="block_size", default="4k", help="Block size"
    )
    parser.add_argument(
        "-i",
        "--iodp",
        dest="iodepth",
        type=int,
        default=128,
        help="number of I/O units to keep in flight against the file",
    )
    parser.add_argument(
        "-o",
        "--dio",
        dest="direct_io",
        type=int,
        default=1,
        help="If direct_io = 1, use non-buffered I/O.",
    )
    parser.add_argument(
        "-x",
        "--max_iops",
        dest="rate_iops",
        type=int,
        default=8000,
        help="Cap the bandwidth to this number of IOPS",
    )
    parser.add_argument(
        "-j",
        "--numjobs",
        dest="numjobs",
        type=int,
        default=1,
        help=" Number of clones (processes/threads performing the same workload) of this job",
    )
    parser.add_argument(
        "-f",
        "--fs",
        dest="type",
        choices=["filesystem", "blkdevice"],
        required=True,
        help="Use disk as a block device or make it use the filesystem, "
        + "choice are 'filesystem' or 'blkdevice'",
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
        default="/root/G8_testing/tests_results/FIO_test",
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
        "-cs",
        "--cloudspaces",
        dest="cloudspaces",
        help="comma separated of cloudspaces ids",
    )
    parser.add_argument(
        "-appid",
        "--application_id",
        dest="application_id",
        required=True,
        help="itsyouonline Application Id",
    )
    parser.add_argument(
        "-secret", "--secret", dest="secret", required=True, help="itsyouonline Secret"
    )

    options = parser.parse_args()
    gevent.signal(signal.SIGQUIT, gevent.kill)
    concurrency = BoundedSemaphore(options.concurrency)
    main(options)
