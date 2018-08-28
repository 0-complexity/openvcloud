#!/usr/bin/env/python3
import sys
import re
import os
from prettytable import PrettyTable
import itertools
import csv
from argparse import ArgumentParser
import requests


def get_vm_ovs_node(vmid, options):
    params = {
        "grant_type": "client_credentials",
        "client_id": options.application_id,
        "client_secret": options.secret,
        "response_type": "id_token",
    }
    jwt = requests.post(
        "https://itsyou.online/v1/oauth/access_token", params=params
    ).content.decode("utf8")
    headers = {"Authorization": "Bearer {}".format(jwt)}

    # make sure vmid is int
    vm = requests.post(
        "{}/restmachine/cloudapi/machines/get".format(options.environment),
        headers=headers,
        json={"machineId": vmid},
    ).json()
    for disk in vm["disks"]:
        if disk["type"] == "D":
            diskd = requests.post(
                "{}/restmachine/cloudapi/disks/get".format(options.environment),
                headers=headers,
                json={"diskId": disk["id"]},
            ).json()
            ovs_ip = re.search("(\d+.){3}(\d+)", diskd["referenceId"])
            break
    return ovs_ip.group()


# vm_ovsip_iops_list.append({'machineId': machineId, 'ovs_ip': ovs_ip, 'iops': total_iops})


def sum_iops_per_ovs(vm_ovsip_iops_list):
    ovs_list = []
    cross_iops_list = []
    final_iops_list = [[]]
    vm_dist_list = []
    for vm in vm_ovsip_iops_list:
        if vm["ovs_ip"] not in ovs_list:
            ovs_list.append(vm["ovs_ip"])
            cross_iops_list.append([vm["iops"]])
            index = ovs_list.index(vm["ovs_ip"])
            vm_dist_list.insert(index, 1)
        else:
            index = ovs_list.index(vm["ovs_ip"])
            cross_iops_list[index].append(vm["iops"])
            temp = vm_dist_list[index]
            vm_dist_list.remove(vm_dist_list[index])
            vm_dist_list.insert(index, temp + 1)
    for ovs_iops in cross_iops_list:
        final_iops_list[0].append(sum(ovs_iops))
    ovs_list.insert(0, "OVS_NODES")
    final_iops_list[0].insert(0, "TOTAL_IOPS")
    vm_dist_list.insert(0, "VMs DISTRIBUTION")
    final_iops_list.append(vm_dist_list)
    return ovs_list, final_iops_list


def results_on_csvfile(csv_file_name, Res_dir, table_string):
    # s=s1.get_string()
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

    with open("%s/%s.csv" % (Res_dir, csv_file_name), "a") as outcsv:
        writer = csv.writer(outcsv)
        writer.writerows(result)


def collect_results(titles, results, Res_dir, filename):
    table = PrettyTable(titles)
    for i in results:
        table.add_row(i)
    table_txt = table.get_string()
    with open("%s/%s.table" % (Res_dir, filename), "a") as file:
        file.write("\n%s" % table_txt)
    results_on_csvfile(filename, Res_dir, table_txt)


def group_separator(line):
    return line == "\n"


def table_print(iter, arrays, Res_dir):
    titles = ["VM_index", "Machine", "Test_type"]
    titles.append("IOPS(%s)" % iter)
    titles.append("cpuload(%s)" % iter)
    titles.append("Testruntime(%s)" % iter)
    table = PrettyTable(titles)
    index = 0
    for c in arrays:
        index += 1
        c.pop(1)
        c.insert(0, index)
        table.add_row(c)
    table_txt = table.get_string()
    with open("%s/total_results.table" % Res_dir, "a") as file:
        file.write("\n%s" % table_txt)

    result = []
    for line in table_txt.splitlines():
        splitdata = line.split("|")
        if len(splitdata) == 1:
            continue  # skip lines with no separators
        linedata = []
        for field in splitdata:
            field = field.strip()
            if field:
                linedata.append(field)
        result.append(linedata)
    match = re.search("/(201.+)", Res_dir)
    with open("%s/%s.csv" % (Res_dir, match.group(1)), "a") as outcsv:
        writer = csv.writer(outcsv)
        writer.writerows(result)


def main(options):
    Res_dir = options.res_dir

    # working from inside Res_dir
    # iterate on each machine results
    # Assuming RAID0 for calculating the total IOPS
    total_iops_list = []
    vm_ovsip_iops_list = []
    for j in os.listdir(os.getcwd()):

        if j.startswith("machine"):
            disks_count = 0
            os.chdir(j)

            avg_total_cpuload = 0
            if os.path.exists("cpuload.txt"):
                file = open("cpuload.txt", "r")
                f = file.read()
                cpuload = re.finditer(
                    r"all\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+"
                    r"\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)",
                    f,
                )
                total_cpuload = [100 - float(s.group(1)) for s in cpuload]
                avg_total_cpuload = round(sum(total_cpuload) / len(total_cpuload), 1)

            iops_list = []
            disks_runtime = []

            vm_bw_r = []
            vm_bw_w = []
            vm_slat_r_min = []
            vm_slat_r_max = []
            vm_slat_r_avg = []
            vm_slat_w_min = []
            vm_slat_w_max = []
            vm_slat_w_avg = []
            vm_disks_results = []

            # iterate on disks_results per machine
            for i in os.listdir(os.getcwd()):
                if i.startswith("result"):
                    disks_count += 1
                    file = open(i, "r")
                    f = file.read()
                    read_match = re.search(r"read :", f)
                    write_match = re.search(r"write:", f)

                    if read_match:
                        match_bw_r = re.search(r"read : io=\S+ bw=(\S+),", f)
                        disk_bw_read = match_bw_r.group(1)  # ex:234KB/s
                        vm_bw_r.append(disk_bw_read)  # remove kb/s

                    if write_match:
                        match_bw_w = re.search(r"write: io=\S+ bw=(\S+),", f)
                        disk_bw_write = match_bw_w.group(1)  # ex:234KB/s
                        vm_bw_w.append(disk_bw_write)  # remove kb/s

                    match_slat = re.finditer(
                        r"slat \((\S+)\): min=(\S+), max=(\S+), avg=\s*(\S+),", f
                    )
                    c = 0  # count to split read_slat from write_slat

                    if write_match and not read_match:
                        c = 1

                    for m in match_slat:
                        slat_unit = m.group(1)  # usec
                        if m.group(2).endswith("K"):
                            slat_min = int(float(m.group(2).replace("K", "")) * 1000)
                        else:
                            slat_min = float(m.group(2))  # 123.23 string
                        if m.group(3).endswith("K"):
                            slat_max = int(float(m.group(3).replace("K", "")) * 1000)
                        else:
                            slat_max = float(m.group(3))  # 123.23 string
                        if m.group(4).endswith("K"):
                            slat_avg = int(float(m.group(4).replace("K", "")) * 1000)
                        else:
                            slat_avg = float(m.group(4))  # 123.23 string

                        if c == 0:
                            vm_slat_r_min.append(slat_min)
                            vm_slat_r_max.append(slat_max)
                            vm_slat_r_avg.append(slat_avg)
                        else:
                            vm_slat_w_min.append(slat_min)
                            vm_slat_w_max.append(slat_max)
                            vm_slat_w_avg.append(slat_avg)
                        c += 1

                    disk_iops = []
                    match = re.finditer(r"iops=([\S]+),", f)
                    # this for loop in case there are iops for write and read
                    for c in match:
                        if c.group(1).endswith("K"):
                            disk_iops.append(
                                int(float(c.group(1).replace("K", "")) * 1000)
                            )
                        else:
                            disk_iops.append(int(c.group(1)))
                    iops_list.append(sum(disk_iops))
                    runt = re.search(r"runt=\s*([\d]+)msec", f)
                    if runt:
                        disks_runtime.append(int(runt.group(1)))
                    else:
                        open("/tmp/d.txt", "w").write(f)
                        disks_runtime.append(-1)
            total_iops = sum(iops_list)

            total_iops_list.append(total_iops)

            runtime = max(disks_runtime) if disks_runtime else 0
            vm_info = re.search("machine([\d.]+)_iter([\d]+)_([\w]+)_", j)
            machineId = vm_info.group(1)
            iteration = vm_info.group(2)
            write_type = vm_info.group(3)

            with open("%s/total_results" % Res_dir, "a") as newfile:
                newfile.write(
                    "\n VM: %s \n Iteration: %s \n Test_type: %s"
                    % (machineId, iteration, write_type)
                )
                newfile.write(
                    "\n IOPS(%s): %s \n Avg_cpuload(%s): %s%% \n test_runtime(%s): %s msec"
                    % (
                        iteration,
                        total_iops,
                        iteration,
                        avg_total_cpuload,
                        iteration,
                        runtime,
                    )
                )
                newfile.write("\n --------------------:-------------------- \n")

            ovs_ip = get_vm_ovs_node(int(machineId), options)
            vm_ovsip_iops_list.append(
                {"machineId": machineId, "ovs_ip": ovs_ip, "iops": total_iops}
            )

            os.chdir("%s" % Res_dir)

            # Info about disks per vm
            vm_bw_r.insert(0, "BW_R")
            vm_slat_r_min.insert(0, "SLAT_R_MIN (%s)" % slat_unit)
            vm_slat_r_max.insert(0, "SLAT_R_MAX (%s)" % slat_unit)
            vm_slat_r_avg.insert(0, "SLAT_R_AVG (%s)" % slat_unit)
            vm_bw_w.insert(0, "BW_W")
            vm_slat_w_min.insert(0, "SLAT_W_MIN (%s)" % slat_unit)
            vm_slat_w_max.insert(0, "SLAT_W_MAX (%s)" % slat_unit)
            vm_slat_w_avg.insert(0, "SLAT_W_AVG (%s)" % slat_unit)

            if read_match:
                vm_disks_results.append(vm_bw_r)
                vm_disks_results.append(vm_slat_r_min)
                vm_disks_results.append(vm_slat_r_max)
                vm_disks_results.append(vm_slat_r_avg)
            if write_match:
                vm_disks_results.append(vm_bw_w)
                vm_disks_results.append(vm_slat_w_min)
                vm_disks_results.append(vm_slat_w_max)
                vm_disks_results.append(vm_slat_w_avg)

            titles = ["disk%s" % (i + 1) for i in range(disks_count)]
            titles.insert(0, "vm-%s" % machineId)
            collect_results(titles, vm_disks_results, Res_dir, "vms_disks_info")

    ovs_list, iops_list = sum_iops_per_ovs(vm_ovsip_iops_list)
    collect_results(ovs_list, iops_list, Res_dir, "ovs_nodes_iops")

    arr = []
    with open("%s/total_results" % Res_dir) as f:
        for key, group in itertools.groupby(f, group_separator):
            row = []
            if not key:
                for item in list(group):
                    field, value = item.split(":")
                    match = re.search("[\d]+", field)
                    value = value.strip()
                    if field == " Iteration":
                        row.append(int(value))
                    else:
                        row.append(value)
                row.pop(6)
                arr.append(row)

    arr.sort(key=lambda x: x[1])
    b = []
    iter = 1
    for a in arr:
        if a[1] == iter:
            b.append(a)
        else:
            b.sort()
            table_print(iter, b, Res_dir)
            iter += 1
            b = []
            b.append(a)
        if a == arr[len(arr) - 1]:
            b.sort()
            table_print(iter, b, Res_dir)
    print(
        "##################### \n TOTAL_IOPS = %s \n#####################"
        % sum(total_iops_list)
    )


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument(
        "-dir", "--resources_dir", dest="res_dir", help="Resources dir", required=True
    )
    parser.add_argument(
        "-env",
        "--environment",
        dest="environment",
        help="OVC environment",
        required=True,
    )
    parser.add_argument(
        "-u", "--user", dest="username", help="ovc username", required=True
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
    main(options)
