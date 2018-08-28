#!/usr/local/bin/jspython
import os
import sys
from JumpScale import j
import ConfigParser
import multiprocessing
import time
import re
import datetime

sys.path.append(os.getcwd())
from utils import utils


config = ConfigParser.ConfigParser()
config.read("Testsuite/3_fio_blktap/Perf_parameters.cfg")
testrun_time = int(config.get("perf_parameters", "testrun_time"))
data_size = int(config.get("perf_parameters", "data_size")) / 3
IO_type = config.get("perf_parameters", "IO_type")
bs = config.get("perf_parameters", "bs")
iodepth = int(config.get("perf_parameters", "iodepth"))
direct_io = int(config.get("perf_parameters", "direct_io"))
rwmixwrite = int(config.get("perf_parameters", "rwmixwrite"))
no_of_disks = int(config.get("perf_parameters", "no_of_disks"))
disk_size = int(config.get("perf_parameters", "disk_size"))
time_diff = int(config.get("perf_parameters", "time_diff"))
ovs_nodes = config.get("perf_parameters", "ovs_nodes")
ovs_nodes_list = ovs_nodes.split("-")
ovs_nodes_No = len(ovs_nodes_list)
Res_dir = config.get("perf_parameters", "Res_dir")
ovs_port = int(config.get("perf_parameters", "ovs_port"))
j.do.execute("mkdir -p %s/" % Res_dir)
j.do.execute("apt-get install fio")

# results directory
hostname = j.do.execute("hostname")[1].replace("\n", "")
test_num = len(os.listdir("%s" % Res_dir)) + 1
test_folder = (
    "/"
    + datetime.datetime.today().strftime("%Y-%m-%d")
    + "_"
    + hostname
    + "_testresults_%s" % test_num
)
Res_dir = Res_dir + test_folder
j.do.execute("mkdir -p %s/" % Res_dir)
j.do.execute("cp Testsuite/3_fio_blktap/Perf_parameters.cfg %s" % Res_dir)

try:
    print("Creating %s disks" % no_of_disks)
    p = 0
    for i in range(no_of_disks):
        j.do.execute(
            "qemu-img create -f raw openvstorage+tcp:%s:%s/archive/disk%s %sG"
            % (ovs_nodes_list[p], ovs_port, (i + 1), disk_size)
        )
        j.do.execute(
            "tap-ctl create -a openvstorage+tcp:%s:%s/archive/disk%s"
            % (ovs_nodes_list[p], ovs_port, (i + 1))
        )
        p += 1
        if p == ovs_nodes_No:
            p = 0

    def run_fio(k):
        j.do.execute(
            "fio --bs=%s --filename=/dev/xen/blktap-2/tapdev%s --iodepth=%s --direct=%s --ioengine=libaio "
            " --gtod_reduce=1 --name=test_iter1 --size=%sM --readwrite=%s --rwmixwrite=%s"
            " --group_reporting  --runtime=%s "
            "--output=%s/disk_%s.out"
            % (
                bs,
                k,
                iodepth,
                direct_io,
                data_size,
                IO_type,
                rwmixwrite,
                testrun_time,
                Res_dir,
                k + 1,
            )
        )

    processes = []
    for k in range(no_of_disks):
        p = multiprocessing.Process(target=run_fio, args=(k,))
        processes.append(p)
    for k in range(len(processes)):
        processes[k].start()
        print("FIO testing has been started on /dev/xen/blktap-2/tapdev%s" % (k))
        time.sleep(time_diff)
    for k in range(len(processes)):
        processes[k].join()
        print("FIO testing has been ended on /dev/xen/blktap-2/tapdev%s" % (k))

    # collect results
    iops_list = []
    disks_runtime = []
    results = []
    k = 1
    # iterate on disks_results per machine
    for i in os.listdir("%s/" % Res_dir):
        if i.startswith("disk"):
            file = open("%s/" % Res_dir + i, "r")
            f = file.read()
            disk_iops = []
            match = re.finditer(r"iops=([\S]+),", f)
            for c in match:
                if c.group(1).endswith("K"):
                    disk_iops.append(int(float(c.group(1).replace("K", "")) * 1000))
                else:
                    disk_iops.append(int(c.group(1)))
            iops_list.append(sum(disk_iops))
            results.append(["disk_%s" % k, sum(disk_iops)])
            runt = re.search(r"runt=\s*([\d]+)msec", f)
            disks_runtime.append(int(runt.group(1)))
            k += 1
    total_iops = sum(iops_list)

    titles = ["Disks", "IOPS"]
    results.append(["Total_IOPS", total_iops])
    utils.collect_results(titles, results, "%s" % Res_dir)
    utils.push_results_to_repo(Res_dir, test_type="fio_alba")

finally:
    # cleaning
    j.do.execute("bash Testsuite/3_fio_blktap/clean.sh")
    j.do.execute(
        "sshpass -p rooter ssh root@%s 'rm -rf /mnt/vmstor/archive/*' "
        % ovs_nodes_list[0]
    )
