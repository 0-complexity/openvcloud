#!/usr/local/bin/jspython
import sys
import os
from JumpScale import j
import ConfigParser
import multiprocessing
import time
from fabric import network
import datetime

sys.path.append(os.getcwd())
from utils import utils


vms_to_run_fio_on = int(sys.argv[1])
config = ConfigParser.ConfigParser()
config.read("Testsuite/1_fio_vms/Perf_parameters.cfg")
USERNAME = config.get("perf_parameters", "username")
No_of_cloudspaces = int(config.get("perf_parameters", "No_of_cloudspaces"))
vms_time_diff = float(config.get("perf_parameters", "vms_time_diff"))
data_size = int(config.get("perf_parameters", "data_size"))
testrun_time = int(config.get("perf_parameters", "testrun_time"))
Res_dir = config.get("perf_parameters", "Res_dir")
no_of_disks = int(config.get("perf_parameters", "no_of_disks"))
rwmixwrite = int(config.get("perf_parameters", "rwmixwrite"))
bs = config.get("perf_parameters", "bs")
iodepth = int(config.get("perf_parameters", "iodepth"))
direct_io = int(config.get("perf_parameters", "direct_io"))
rate_iops = int(config.get("perf_parameters", "rate_iops"))
numjobs = int(config.get("perf_parameters", "numjobs"))
IO_type = config.get("perf_parameters", "IO_type")
hostname = j.sal.process.execute("hostname")[1].replace("\n", "")
test_num = len(os.listdir("%s" % Res_dir)) + 1
test_folder = (
    "/"
    + datetime.datetime.today().strftime("%Y-%m-%d")
    + "_"
    + hostname
    + "_testresults_%s" % test_num
)
Res_dir = Res_dir + test_folder

if not j.sal.fs.exists("%s" % Res_dir):
    j.sal.process.execute("mkdir -p %s" % Res_dir)
j.sal.process.execute("cp Testsuite/1_fio_vms/Perf_parameters.cfg %s" % Res_dir)
j.sal.process.execute("cp /test_results/VMs_creation_time.csv %s" % Res_dir)

ccl = j.clients.osis.getNamespace("cloudbroker")
pcl = j.clients.portal.getByInstance("main")
vms_list = []
for n in range(No_of_cloudspaces):
    cloudspaceId = ccl.cloudspace.search(
        {"acl.userGroupId": USERNAME, "status": "DEPLOYED"}
    )[n + 1]["id"]
    portforwards = pcl.actors.cloudapi.portforwarding.list(cloudspaceId=cloudspaceId)
    for pi in portforwards:
        vms_list.append({pi["machineId"]: [pi["publicIp"], pi["publicPort"], IO_type]})

iteration_no = 1
# Only one iteration will be done
network.disconnect_all()
# terminate all connections in case they are there
processes = []
i = 0
for iter_on_vms in vms_list:
    p = multiprocessing.Process(
        target=utils.FIO_test,
        args=(
            iter_on_vms,
            pcl,
            data_size,
            testrun_time,
            Res_dir,
            iteration_no,
            no_of_disks,
            rwmixwrite,
            bs,
            iodepth,
            direct_io,
            rate_iops,
            numjobs,
        ),
    )
    processes.append(p)
    i += 1
    if i == vms_to_run_fio_on:
        break
for l in range(len(processes)):
    dict = vms_list[l]
    processes[l].start()
    print("FIO testing has been started on machine: %s" % dict.keys()[0])
    time.sleep(vms_time_diff)
for k in range(len(processes)):
    dict = vms_list[k]
    processes[k].join()
    print("FIO testing has been ended on machine: %s" % dict.keys()[0])

for vm in vms_list:
    machineId = vm.keys()[0]
    cloudspace_publicip = vm[machineId][0]
    cloudspace_publicport = vm[machineId][1]
    j.sal.process.execute(
        'ssh-keygen -f "/root/.ssh/known_hosts" -R [%s]:%s'
        % (cloudspace_publicip, cloudspace_publicport)
    )

j.sal.process.execute("cp Testsuite/1_fio_vms/collect_results.py %s" % Res_dir)
j.sal.fs.changeDir("%s" % Res_dir)
j.sal.process.execute("python collect_results.py %s" % Res_dir)
utils.push_results_to_repo(Res_dir, test_type="demo_run_fio")
