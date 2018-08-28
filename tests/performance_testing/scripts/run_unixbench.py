#!/usr/bin/python3
from libtest import (
    run_cmd_via_gevent,
    wait_until_remote_is_listening,
    safe_get_vm,
    check_package,
    push_results_to_repo,
    get_logger,
)
import gevent
from gevent.lock import BoundedSemaphore
import signal
from optparse import OptionParser
import os
import datetime
import csv
import re
import time
from ovc_client import Client

matcher = re.compile(r"System Benchmarks Index Score\s+([\d.]+)")
logger = get_logger("run_unixbench")
machines = dict()


def results_on_csvfile(csv_file_name, result_dir, table_string):
    result = []
    for line in table_string.splitlines():
        splitdata = line.split("|")
        if len(splitdata) == 1:
            continue  # skip lines with no separators
        linedata = []
        for field in splitdata:
            field = field.strip()
            if field:
                linedata.append(field)
        result.append(linedata)

    with open("{}/{}.csv".format(result_dir, csv_file_name), "a") as outcsv:
        writer = csv.writer(outcsv)
        writer.writerows(result)


def collect_results(titles, results, result_dir, filename):
    # collects results in a table
    from prettytable import PrettyTable

    table = PrettyTable(titles)
    for i in results:
        table.add_row(i)
    table_txt = table.get_string()
    with open("{}/results.table".format(result_dir), "a") as file:
        file.write("\n{}".format(table_txt))
    results_on_csvfile(filename, result_dir, table_txt)


def prepare_unixbench_test(options, ovc, cpu_cores, machine_id, publicip, publicport):
    print("Preparing unixbench test on machine {}".format(machine_id))
    machine = safe_get_vm(ovc, concurrency, machine_id)
    machines[machine_id] = machine["name"]
    account = machine["accounts"][0]

    wait_until_remote_is_listening(publicip, int(publicport), True, machine_id)

    # templ = 'sshpass -p{} scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
    # templ += '-P {} {}/2_Unixbench2_test/2_machine_script.py  {}@{}:'
    # cmd = templ.format(account['password'], publicport, options.testsuite, account['login'], publicip)
    # run_cmd_via_gevent(cmd)

    return machine_id, publicip, publicport, account, cpu_cores


def unixbench_test(
    options, count, machine_id, publicip, publicport, account, cpu_cores
):
    gevent.sleep(options.time_interval * count)
    print("unixbench testing has been started on machine: {}".format(machine_id))
    templ = 'sshpass -p "{}" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -p {} {}@{} '
    templ += ' "cd /home/cloudscalers/UnixBench; echo {} | sudo -S ./Run -c {} -i 1"'
    cmd = templ.format(
        account["password"],
        publicport,
        account["login"],
        publicip,
        account["password"],
        cpu_cores,
    )
    results = list()
    start = time.time()
    while start + options.test_runtime > time.time():
        output = run_cmd_via_gevent(cmd)
        match = None
        for line in output.splitlines():
            m = matcher.match(line)
            if m:
                match = m
                break
        if match:
            result = float(match.group(1))
            results.append((time.time(), result))
            print("Machine {} reports score of {}".format(machine_id, result))
        else:
            logger.error("Unixbench did not return result:\n\n{}".format(output))

    return machine_id, sum((r[1] for r in results)) / len(results), results


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
    test_dir += "_" + hostname + "_testresults_{}".format(test_num)
    results_dir = options.results_dir + test_dir
    run_cmd_via_gevent("mkdir -p {}".format(results_dir))

    # list virtual and deployed cloudspaces
    vms = []
    vms_index = set()
    ovc = Client(options.environment, options.application_id, options.secret)
    cloudspaces_per_user = ovc.request("cloudapi/cloudspaces/list")
    for cs in cloudspaces_per_user:
        portforwards = ovc.request(
            "cloudapi/portforwarding/list", cloudspaceId=cs["id"]
        )
        for pi in portforwards:
            if "machineId" in pi and not pi["machineId"] in vms_index:
                vms.append([pi["machineId"], pi["publicIp"], pi["publicPort"]])
                vms_index.add(pi["machineId"])

    if len(vms) < options.required_vms:
        print("Not enough vms available to run this test.")
        return
    vms = vms[: options.required_vms]

    # getting bootdisk size, cpu and memory used during vms creatian (for any vm)
    machine = safe_get_vm(ovc, concurrency, pi["machineId"])
    bootdisk = machine["disks"][0]["sizeMax"]
    size_id = machine["sizeid"]
    sizes = ovc.request("cloudapi/sizes/list", cloudspaceId=cs["id"])
    memory = next((i for i in sizes if i["id"] == size_id), False)["memory"]
    cpu = next((i for i in sizes if i["id"] == size_id), False)["vcpus"]

    # prepare unixbench tests
    prepare_jobs = [
        gevent.spawn(prepare_unixbench_test, options, ovc, cpu, *vm) for vm in vms
    ]
    gevent.joinall(prepare_jobs)

    # run unixbench tests
    run_jobs = [
        gevent.spawn(unixbench_test, options, c, *job.value)
        for job, c in zip(*[prepare_jobs, range(len(prepare_jobs))])
        if job.value is not None
    ]
    gevent.joinall(run_jobs)

    raw_results = [job.value for job in run_jobs if job.value]
    raw_results.sort(key=lambda x: x[1])
    results = list()
    index = 0
    for s in raw_results:
        index += 1
        results.append(
            [
                index,
                "{} (id={})".format(machines.get(s[0], s[0]), s[0]),
                cpu,
                memory,
                bootdisk,
                s[1],
            ]
        )
    titles = ["Index", "VM", "CPU's", "Memory(MB)", "HDD(GB)", "Avg. Unixbench Score"]
    collect_results(titles, results, results_dir, "average-results")
    titles = ["VM", "Timestamp (epoch)", "Score"]
    results = list()
    for result in raw_results:
        machine_id, avg_score, scores = result
        for timestamp, score in scores:
            results.append(
                [
                    "{} (id={})".format(
                        machines.get(machine_id, machine_id), machine_id
                    ),
                    timestamp,
                    score,
                ]
            )
    collect_results(titles, results, results_dir, "all-results")

    # report results
    with open(os.path.join(results_dir, "parameters.md"), "w") as params:
        params.write("# Parameters\n\n")
        for key, value in vars(options).items():
            params.write("- **{}**: {}\n".format(key, value))

    # pushing results to env_repo
    push_results_to_repo(results_dir, options.environment)


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
        "-v",
        "--vms",
        dest="required_vms",
        type="int",
        default=2,
        help=" selected number of virtual machines to run unixbench on",
    )
    parser.add_option(
        "-t",
        "--runtime",
        dest="test_runtime",
        type="int",
        default=100,
        help="duration for running unixbecnh (in secs)",
    )
    parser.add_option(
        "-d",
        "--interval",
        dest="time_interval",
        type="int",
        default=0.5,
        help="time interval between starting unixbench on 2 successive machines   (in secs)",
    )
    parser.add_option(
        "-r",
        "--rdir",
        dest="results_dir",
        type="string",
        default="/root/G8_testing/tests_results/unixbench",
        help="absolute path for results directory",
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
        "-s",
        "--ts",
        dest="testsuite",
        default="../Testsuite",
        type="string",
        help="location to find Testsuite directory",
    )
    parser.add_option(
        "-a",
        "--application_id",
        dest="application_id",
        help="itsyouonline Application Id",
    )
    parser.add_option("-s", "--secret", dest="secret", help="itsyouonline Secret")

    (options, args) = parser.parse_args()
    if not options.username or not options.password or not options.environment:
        parser.print_usage()
    else:
        gevent.signal(signal.SIGQUIT, gevent.kill)
        concurrency = BoundedSemaphore(options.concurrency)
        main(options)
