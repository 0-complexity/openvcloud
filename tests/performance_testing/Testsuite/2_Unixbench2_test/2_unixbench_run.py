#!/usr/local/bin/jspython
from JumpScale import j
import sys
import os
from fabric import network
import time
import multiprocessing
import ConfigParser
import datetime


vms_to_run_unixbench_on = int(sys.argv[1])
config = ConfigParser.ConfigParser()
config.read("Testsuite/2_Unixbench2_test/parameters.cfg")
No_of_cloudspaces = int(config.get("parameters", "No_of_cloudspaces"))
cpus = int(config.get("parameters", "cpus"))
Bdisksize = int(config.get("parameters", "Bdisksize"))
memory = int(config.get("parameters", "memory"))
vms_time_diff = int(config.get("parameters", "vms_time_diff"))
unixbench_run_times = int(config.get("parameters", "unixbench_run_times"))
Res_dir = config.get("parameters", "Res_dir")

j.do.execute("mkdir -p %s" % Res_dir)
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

if not j.do.exists("%s" % Res_dir):
    j.do.execute("mkdir -p %s" % Res_dir)
sys.path.append(os.getcwd())
from utils import utils

try:
    ## getting created machines
    USERNAME = "unixbench2testuser"
    ccl = j.clients.osis.getNamespace("cloudbroker")
    pcl = j.clients.portal.getByInstance("main")

    machines = []
    for n in range(No_of_cloudspaces):
        cloudspaceId = ccl.cloudspace.search(
            {"acl.userGroupId": USERNAME, "status": "DEPLOYED"}
        )[n + 1]["id"]
        portforwards = pcl.actors.cloudapi.portforwarding.list(
            cloudspaceId=cloudspaceId
        )
        for pi in portforwards:
            machines.append([pi["machineId"], pi["publicIp"], pi["publicPort"]])

    # post results for first machine
    print("running unixbench on the first machine only")
    VM1_score = utils.Run_unixbench(machines[0], cpus, pcl)
    first_machineId = machines[0][0]
    titles = ["Index", "VM", "CPU's", "Memory(MB)", "HDD(GB)", "Avg. Unixbench Score"]
    results = [[1, first_machineId, cpus, memory, Bdisksize, VM1_score]]
    utils.collect_results(titles, results, "%s" % Res_dir)
    network.disconnect_all()

    for i in range(unixbench_run_times):
        network.disconnect_all()
        q = multiprocessing.Queue()
        processes = []
        res_arr = []
        c = 0
        for vm in machines:
            p = multiprocessing.Process(
                target=utils.Run_unixbench, args=(vm, cpus, pcl, q)
            )
            processes.append(p)
            c += 1
            if c == vms_to_run_unixbench_on:
                break
        print("running unixbench on all required machines")
        for l in range(len(processes)):
            processes[l].start()
            time.sleep(vms_time_diff)
        for k in range(len(processes)):
            processes[k].join()
        for n in range(len(processes)):
            res_arr.append(q.get())

        res_arr.sort()
        # first machine unixbench score for iteration i
        results = []
        for s in res_arr:
            results.append([res_arr.index(s) + 1, s[0], cpus, memory, Bdisksize, s[1]])
        utils.collect_results(titles, results, "%s" % Res_dir)

    # Removing vms fingerprints from known hosts
    for vm in machines:
        cs_ip = vm[1]
        cs_pp = vm[2]
        j.do.execute(
            'ssh-keygen -f "/root/.ssh/known_hosts" -R [%s]:%s' % (cs_ip, cs_pp)
        )

except:
    print("Found problems during running the test.. removing results directory..")
    for vm in machines:
        cs_ip = vm[1]
        cs_pp = vm[2]
        j.do.execute(
            'ssh-keygen -f "/root/.ssh/known_hosts" -R [%s]:%s' % (cs_ip, cs_pp)
        )
    j.do.execute("rm -rf %s" % Res_dir)
    raise
utils.push_results_to_repo(Res_dir)
