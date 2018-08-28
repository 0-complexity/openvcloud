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
config.read("Testsuite/10_fio_alba/Perf_parameters.cfg")
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
Res_dir = config.get("perf_parameters", "Res_dir")
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
j.do.execute("cp Testsuite/10_fio_alba/Perf_parameters.cfg %s" % Res_dir)

try:
    print("Creating 10 disks on the fuse file system")
    for i in range(no_of_disks):
        j.do.execute("truncate -s %sG /mnt/vmstor/test_disk%s.raw" % (disk_size, i + 1))
        j.do.execute("losetup /dev/loop%s /mnt/vmstor/test_disk%s.raw" % (i, i + 1))
        j.do.execute("mkfs.ext4 /dev/loop%s" % i)
        j.do.execute(
            "mkdir -p /var/tmp/disk_%s/" % (i + 1)
        )  # check the mounting point if it is oki to be out of the /mnt/vmstor
        j.do.execute("mount /dev/loop%s /var/tmp/disk_%s/" % (i, i + 1))

    def run_fio(k):
        j.do.execute(
            "fio --bs=%s --iodepth=%s --direct=%s --ioengine=libaio "
            " --gtod_reduce=1 --name=test_iter1 --size=%sM --readwrite=%s --rwmixwrite=%s"
            " --numjobs=3 --group_reporting --directory=/var/tmp/disk_%s --runtime=%s "
            "--output=%s/disk_%s.out"
            % (
                bs,
                iodepth,
                direct_io,
                data_size,
                IO_type,
                rwmixwrite,
                k + 1,
                testrun_time,
                Res_dir,
                k + 1,
            )
        )

    processes = []
    for k in range(no_of_disks):
        p = multiprocessing.Process(target=run_fio, args=(k,))
        processes.append(p)
        k += 1
    for k in range(len(processes)):
        processes[k].start()
        print("FIO testing has been started on /mnt/vmstor/test_disk%s.raw" % (k + 1))
        time.sleep(time_diff)
    for k in range(len(processes)):
        processes[k].join()
        print("FIO testing has been ended on /mnt/vmstor/test_disk%s.raw" % (k + 1))

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
    # utils.push_results_to_repo(Res_dir, test_type='fio_alba')

    # cleaning
    for p in range(no_of_disks):
        j.do.execute("umount /dev/loop%s" % p)
        j.do.execute("losetup -d /dev/loop%s" % p)
        j.do.execute("rm -rf /var/tmp/disk_%s" % (p + 1))
        j.do.execute("rm -rf /mnt/vmstor/test_disk%s.raw" % (p + 1))

except Exception as e:
    print("Error: %s" % e)
    print("Error args: %s" % e.args)
    j.do.execute("rm -rf %s" % Res_dir)
    for p in range(no_of_disks):
        try:
            j.do.execute("umount /dev/loop%s" % p)
        except RuntimeError:
            print("handling Expected Error: /dev/loop1: not mounted")
        try:
            j.do.execute("losetup -d /dev/loop%s" % p)
        except RuntimeError:
            print(
                "handling Expected Error: can't delete device /dev/loop0: No such device or address"
            )
        j.do.execute("rm -rf /var/tmp/disk_%s" % (p + 1))
        j.do.execute("rm -rf /mnt/vmstor/test_disk%s.raw" % (p + 1))
