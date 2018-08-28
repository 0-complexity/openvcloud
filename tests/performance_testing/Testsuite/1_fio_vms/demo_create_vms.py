#!/usr/local/bin/jspython
import sys
import os
from JumpScale import j
import ConfigParser
import uuid


def main():
    ccl = j.clients.osis.getNamespace('cloudbroker')
    pcl = j.clients.portal.getByInstance('main')
    scl = j.clients.osis.getNamespace('system')

    No_of_vms= int(sys.argv[1])

    #run the setup_test from inside the repo so the file could be parsed
    config = ConfigParser.ConfigParser()
    config.read("Testsuite/1_fio_vms/Perf_parameters.cfg")
    used_stacks = int(config.get("perf_parameters", "used_stacks"))
    memory = int(config.get("perf_parameters", "memory"))
    cpu = int(config.get("perf_parameters", "cpu"))
    Bdisksize = int(config.get("perf_parameters", "Bdisksize"))
    no_of_disks = int(config.get("perf_parameters", "no_of_disks"))
    data_disksize = int(config.get("perf_parameters", "data_disksize"))
    No_of_cloudspaces = int(config.get("perf_parameters", "No_of_cloudspaces"))
    USERNAME = config.get("perf_parameters", "username")
    ACCOUNTNAME = str(uuid.uuid4())[0:8]
    Res_dir = config.get("perf_parameters", "Res_dir")
    j.sal.process.execute('mkdir -p %s' % Res_dir)
    j.sal.fs.exists('/test_results'):
        j.sal.process.execute('rm -rf /test_results/*')
    j.sal.process.execute('mkdir -p /test_results')
    sys.path.append(os.getcwd())
    from utils import utils
    j.sal.process.execute('apt-get install sshpass')

    stacks = utils.remove_ovsnodes_from_stacks(utils.get_stacks(ccl), ccl)
    #current_stack = ccl.stack.search({'referenceId': str(j.application.whoAmI.nid), 'gid': j.application.whoAmI.gid})[1]
    #stacks.remove(current_stack['id'])
    stacks = stacks[0:used_stacks]
    vm_specs = [no_of_disks, data_disksize, Bdisksize, memory, cpu]
    cloudspace_publicport = 7000


    email = "%s@test.com" % str(uuid.uuid4())[0:8]
    utils.create_user(USERNAME, email,  pcl, scl)

    cloudspaces_list=[]
    accountId = utils.create_account(USERNAME, email, ACCOUNTNAME, ccl, pcl)
    for i in range(No_of_cloudspaces):
        cloudspace = utils.create_cloudspace(accountId, USERNAME, ccl, pcl, cs_name='default_%s'%i)
        cloudspaces_list.append(cloudspace)


    #cloudspace = utils.create_account_cloudspace(USERNAME, email, ACCOUNTNAME, ccl, pcl, scl)

    vms_list = []
    i=0
    c=0
    while i < No_of_vms:
        for stackId in stacks:
            cloudspace_publicport += 1
            [machineId, cloudspace_publicip] = utils.create_machine_onStack(stackId, cloudspaces_list[c], '_%s' %i, ccl, pcl, scl,
                                                                          vm_specs, cloudspace_publicport, Res_dir='/test_results')
            c += 1
            if c==No_of_cloudspaces:
                c=0
            vms_list.append({machineId: [cloudspace_publicip, cloudspace_publicport]})
            i += 1
            if i == No_of_vms:
                break
    #Removing vms fingerprints entries from known hosts
    for vm in vms_list:
        machineId = vm.keys()[0]
        cloudspace_publicip=vm[machineId][0]
        cloudspace_publicport=vm[machineId][1]
        j.sal.process.execute('ssh-keygen -f "/root/.ssh/known_hosts" -R [%s]:%s'
                     %(cloudspace_publicip, cloudspace_publicport))

if __name__ == "__main__":
    main()
