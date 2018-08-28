#!/usr/local/bin/jspython
from JumpScale import j
import uuid
import sys
import os
import time
import multiprocessing
import ConfigParser


def main():
    config = ConfigParser.ConfigParser()
    config.read("Testsuite/2_Unixbench2_test/parameters.cfg")
    No_of_cloudspaces = int(config.get("parameters", "No_of_cloudspaces"))
    VMs = int(config.get("parameters", "VMs"))
    cpus = int(config.get("parameters", "cpus"))
    memory = int(config.get("parameters", "memory"))
    Bdisksize = int(config.get("parameters", "Bdisksize"))
    no_of_disks = 0
    data_disksize = 0
    vm_specs = [no_of_disks, data_disksize, Bdisksize, memory, cpus]

    sys.path.append(os.getcwd())
    from utils import utils

    ccl = j.clients.osis.getNamespace("cloudbroker")
    pcl = j.clients.portal.getByInstance("main")
    scl = j.clients.osis.getNamespace("system")

    USERNAME = "unixbench2testuser"
    email = "%s@test.com" % str(uuid.uuid4())[0:8]
    utils.create_user(USERNAME, email, pcl, scl)
    ACCOUNTNAME = str(uuid.uuid4())[0:8]
    accountId = utils.create_account(USERNAME, email, ACCOUNTNAME, ccl, pcl)

    cloudspaces_list = []
    for i in range(No_of_cloudspaces):
        cloudspace = utils.create_cloudspace(
            accountId, USERNAME, ccl, pcl, cs_name="default_%s" % i
        )
        cloudspaces_list.append(cloudspace)
    cloudspace_publicport = 2000

    stacks = utils.get_stacks(ccl)
    current_stack = ccl.stack.search(
        {"referenceId": str(j.application.whoAmI.nid), "gid": j.application.whoAmI.gid}
    )[1]
    stacks.remove(current_stack["id"])
    stacks_temp = []

    def select_stackid():
        global stacks_temp
        ns = list(set(stacks) - set(stacks_temp))
        stacks_temp.append(ns[0])
        if len(stacks_temp) == len(stacks):
            stacks_temp = []
        return ns[0]

    print("creating %s vms" % VMs)
    machines = []
    iteration = 1
    c = 0
    for k in range(VMs):
        [machineId, cloudspace_ip] = utils.create_machine_onStack(
            select_stackid(),
            cloudspaces_list[c],
            iteration,
            ccl,
            pcl,
            scl,
            vm_specs,
            cloudspace_publicport,
            Res_dir="test_res",
        )
        machines.append(
            [machineId, cloudspace_ip, cloudspace_publicport, cloudspaces_list[c]]
        )
        c += 1
        if c == No_of_cloudspaces:
            c = 0
        iteration += 1
        cloudspace_publicport += 1

    # installing unixbench on machines
    print("Installing Unixbench on required machines")
    processes = []
    for vm in machines:
        vmid = vm[0]
        cs = vm[3]
        cs_pp = vm[2]
        p = multiprocessing.Process(
            target=utils.Install_unixbench,
            args=(
                vmid,
                cs,
                cs_pp,
                pcl,
                "Testsuite/2_Unixbench2_test/2_machine_script.py",
            ),
        )
        processes.append(p)
    for l in range(len(processes)):
        processes[l].start()
        time.sleep(1)
    for k in range(len(processes)):
        processes[k].join()

    # removing finger prints
    for vm in machines:
        cs_ip = vm[1]
        cs_pp = vm[2]
        j.do.execute(
            'ssh-keygen -f "/root/.ssh/known_hosts" -R [%s]:%s' % (cs_ip, cs_pp)
        )


if __name__ == "__main__":
    stacks_temp = []
    try:
        main()
    except:
        print("Found problems during running creating the vms")
        j.do.execute("jspython scripts/tear_down.py unixbench2testuser")
