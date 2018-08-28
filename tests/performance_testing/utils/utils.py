from JumpScale import j
import netaddr
import time
from JumpScale.portal.portal.PortalClient2 import ApiError
from prettytable import PrettyTable
import csv
import re
import uuid
import ConfigParser


def get_stacks(ccl):
    return ccl.stack.list()

def remove_ovsnodes_from_stacks(stacks_list,ccl):
    for stk in ccl.stack.search({}):
        if type(stk)==int:
            continue
        if stk['name'].startswith('ovs'):
            stacks_list.remove(stk['id'])
    return stacks_list

def create_user(USERNAME, email, pcl, scl):
    print "Creating User with username %s" %USERNAME
    pcl.actors.cloudbroker.user.create(USERNAME, email, 'gig12345')
    user = scl.user.get(USERNAME)
    user.groups.extend([u'level1', u'level2', u'level3', u'admin',u'finance',u'ovs_admin',u'user'])
    scl.user.set(user)

def create_account_cloudspace(USERNAME, email, ACCOUNTNAME, ccl, pcl, scl, cs_name=''):
    print 'Creating Account with accountname %s' % ACCOUNTNAME
    accountId = pcl.actors.cloudbroker.account.create(ACCOUNTNAME, USERNAME, email)
    cloudspace = create_cloudspace(accountId, USERNAME, ccl, pcl, cs_name='')
    return cloudspace

def create_machine_onStack(stackid, cloudspace, iteration, ccl, pcl, scl, vm_specs, cs_publicport=0,
                           telegraf=None, Res_dir=None, queue=None):

    images = ccl.image.search({'name': 'Ubuntu 14.04 x64'})[1:]
    if not images:
        return [{'message': "Image not available (yet)", 'category': 'Storage Test', 'state': "ERROR"}]
    imageId = images[0]['id']

    size = ccl.size.search({'memory': vm_specs[3], 'vcpus': vm_specs[4]})
    if size[0] == 0:
        size = ccl.size.search({'memory': 2048, 'vcpus': 2})[1]
    else:
        size = ccl.size.search({'memory': vm_specs[3], 'vcpus': vm_specs[4]})[1]

    sizeId = size['id']

    if vm_specs[2] in [10, 20, 50, 100, 250, 500, 1000, 2000]:
        boot_diskSize = vm_specs[2]
    else:
        boot_diskSize = size['disks'][3]

    datadisks_list = [vm_specs[1] for x in range(vm_specs[0])]

    cloudspace_publicip = str(netaddr.IPNetwork(cloudspace['publicipaddress']).ip)
    print('Creating new machine...')
    t1 = time.time()

    try:
        machineId = pcl.actors.cloudbroker.machine.createOnStack(cloudspaceId=cloudspace['id'],
                                                             name='node%s%s' % (stackid, iteration), imageId=imageId, sizeId=sizeId,
                                                             disksize=boot_diskSize, stackid=stackid, datadisks=datadisks_list)
    except:
        print('   |--failed to create the machine with error')
        vm = ccl.vmachine.search({'name': 'node%s%s'% (stackid, iteration), 'cloudspaceId': cloudspace['id']})
        if vm[0] != 0:
            ccl.vmachine.delete(vm[1]['id'])
        print('   |--trying to create the machine once more')
        machineId = pcl.actors.cloudbroker.machine.createOnStack(cloudspaceId=cloudspace['id'],
                                                                     name='node%s%s' % (stackid, iteration),
                                                                     imageId=imageId, sizeId=sizeId,
                                                                     disksize=boot_diskSize, stackid=stackid,
                                                                     datadisks=datadisks_list)

    print('   |--finished creating machine: %s' % machineId)
    if queue:
        #needed for 4_unixbench for parallel execution
        queue.put([machineId, cloudspace_publicip, cs_publicport, cloudspace])
    if Res_dir != 'wait_for_VMIP':
        now = time.time()
        ip = 'Undefined'
        print '   |--Waiting for IP for VM: node%s%s' % (stackid, iteration)
        while now + 300 > time.time() and ip == 'Undefined':
            time.sleep(1)
            machine = run_again_if_failed(pcl.actors.cloudapi.machines.get, machineId=machineId)
            ip = machine['interfaces'][0]['ipAddress']
        try:
            time.sleep(5)
            pcl.actors.cloudapi.portforwarding.create(cloudspace['id'], cloudspace_publicip, cs_publicport, machineId, 22, 'tcp')
        except:
            time.sleep(2)
            pcl.actors.cloudapi.portforwarding.create(cloudspace['id'], cloudspace_publicip, cs_publicport, machineId, 22, 'tcp')
            time.sleep(50)

        if not j.system.net.waitConnectionTest(cloudspace_publicip, cs_publicport, 60):
            print 'Could not connect to VM over public interface'
    if not Res_dir or Res_dir=='wait_for_VMIP':
        return machineId
    elif Res_dir=='test_res':
        return [machineId, cloudspace_publicip]
    else:
        t2 = time.time()
        time_creating_vm = round(t2-t1, 2)
        j.do.execute('(echo "VM:;%s;creation time:;%s; ;") | sed "s/;/,/g" >> %s/VMs_creation_time.csv' %(machineId, time_creating_vm, Res_dir))
        if telegraf:
            setup_machine(cloudspace, machineId, cs_publicport, pcl, vm_specs[0], telegraf='install')
        else:
            setup_machine(cloudspace, machineId, cs_publicport, pcl, vm_specs[0])
        return [machineId, cloudspace_publicip]

def setup_machine(cloudspace, machineId, cs_publicport, pcl, no_of_disks, fio=None, telegraf=None):
    print ('   |--setup machine:%s' %machineId)
    cloudspace_publicip = str(netaddr.IPNetwork(cloudspace['publicipaddress']).ip)

    machine = pcl.actors.cloudapi.machines.get(machineId)
    account = machine['accounts'][0]

    if not j.system.net.waitConnectionTest(cloudspace_publicip, cs_publicport, 40):
        print 'Could not connect to VM over public interface'
    else:
        connection = j.remote.cuisine.connect(cloudspace_publicip, cs_publicport, account['password'], account['login'])
        connection.fabric.state.output["running"]=False
        connection.fabric.state.output["stdout"]=False
        connection.user(account['login'])
        connection.apt_get('update')
        connection.apt_get('install fio')
        if fio != 'onlyfio':
            connection.apt_get('install sysstat')
            #machine_mount_disks(connection, account, machineId, no_of_disks)
            #format_disks(connection, account, machineId, no_of_disks)
        if telegraf:
            connection.run('echo %s | sudo -S wget https://dl.influxdata.com/telegraf/releases/telegraf_1.0.0-beta3_amd64.deb' %account['password'])
            connection.run('echo %s | sudo -S dpkg -i telegraf_1.0.0-beta3_amd64.deb' %account['password'])
            connection.run('echo %s | sudo -S chmod 666 /etc/telegraf/telegraf.conf'%account['password'])
            j.do.execute('sshpass -p%s scp -r -o \'StrictHostKeyChecking=no \' -P %s telegraf.conf %s@%s:/etc/telegraf'
                     %(account['password'], cs_publicport, account['login'], cloudspace_publicip))
            time.sleep(2)
            connection.run('echo %s | sudo -S service telegraf restart; sleep 4' %account['password'], timeout=10)

def format_disks(connection, account, machineId, no_of_disks=6):
    list = ['b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
    print('   |--formating disks for machine:%s' % machineId)
    for i in range(no_of_disks):
        connection.run('echo %s | sudo -S mkfs.ext4 /dev/vd%s' %(account['password'],list[i]))
    print('   |--finished formating')


def machine_mount_disks(connection, account, machineId, no_of_disks=6):
    list=['b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
    print('   |--mounting disks for machine:%s' %machineId)

    for i in range(no_of_disks):
        connection.run('echo %s | sudo -S echo -n ; echo n; echo p; echo 1; echo -ne \'\n\'; echo -ne \'\n\'; echo w | sudo fdisk /dev/vd%s' %(account['password'],list[i]))
        connection.run('echo %s | sudo -S mkfs.ext4 /dev/vd%s' %(account['password'],list[i]))
        connection.run('echo %s | sudo -S mkdir -p /mnt/disk_%s' %(account['password'],list[i]))
        connection.run('echo %s | sudo -S mount /dev/vd%s /mnt/disk_%s' %(account['password'],list[i], list[i]))
    print('   |--finished mounting')

def FIO_test(vm_pubip_pubport, pcl, data_size, testrun_time, Res_dir, iteration,
             no_of_disks, rwmixwrite, bs, iodepth, direct_io, rate_iops, numjobs):
    machineId = vm_pubip_pubport.keys()[0]
    cloudspace_publicip = vm_pubip_pubport.values()[0][0]
    cs_publicport = vm_pubip_pubport.values()[0][1]
    write_type = vm_pubip_pubport.values()[0][2]

    machine = pcl.actors.cloudapi.machines.get(machineId)
    account = machine['accounts'][0]

    if not j.system.net.waitConnectionTest(cloudspace_publicip, cs_publicport, 20):
        print 'Could not connect to VM over public interface'
    else:
        connection = j.remote.cuisine.connect(cloudspace_publicip, cs_publicport, account['password'], account['login'])
        connection.user(account['login'])
        connection.fabric.state.output["running"]=False
        connection.fabric.state.output["stdout"]=False
        j.do.execute('sshpass -p%s scp -o \'StrictHostKeyChecking=no\' -P %s Testsuite/1_fio_vms/Machine_script.py  %s@%s:'
                     %(account['password'], cs_publicport, account['login'], cloudspace_publicip))
        connection.run('python Machine_script.py %s %s %s %s %s %s %s %s %s %s %s %s %s' %(testrun_time, machineId,
                        account['password'], iteration, no_of_disks, data_size, write_type, bs, iodepth, direct_io, rwmixwrite, rate_iops, numjobs))
        j.do.execute('sshpass -p%s scp -r -o \'StrictHostKeyChecking=no \' -P %s  %s@%s:machine%s_iter%s_%s_results %s/'
                     %(account['password'], cs_publicport, account['login'], cloudspace_publicip, machineId, iteration, write_type, Res_dir))
        #list=['b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k']
        #for i in range(no_of_disks):
            #connection.run('echo %s | sudo -S umount /dev/vd%s ' %(account['password'],list[i]))
            #connection.run('echo %s | sudo -S mkfs.ext4 /dev/vd%s' %(account['password'],list[i]))
            #connection.run('echo %s | sudo -S mount /dev/vd%s /mnt/disk_%s' %(account['password'],list[i], list[i]))




# These utils is used for the testsuite

def create_account(USERNAME, email, ACCOUNTNAME, ccl, pcl):

    print 'Creating Account with accountname %s' % ACCOUNTNAME
    accountId = pcl.actors.cloudbroker.account.create(ACCOUNTNAME, USERNAME, email)
    return accountId

def create_cloudspace(accountId, username, ccl, pcl, cs_name=''):
        loc = ccl.location.search({})[1]['locationCode']
        cloudspace_id = pcl.actors.cloudapi.cloudspaces.create(accountId=accountId, location=loc,
                                                              name=cs_name or 'default', access=username)
        print 'Creating and deploying CloudSpace...'
        run_again_if_failed(pcl.actors.cloudbroker.cloudspace.deployVFW, cloudspaceId=cloudspace_id)
        # retreive cloudspace with Public IP set
        cloudspace = ccl.cloudspace.get(cloudspace_id).dump()
        return cloudspace

#install unixbench on a given machine
def Install_unixbench(machineId, cloudspace, cs_publicport, pcl, sendscript=None):
    print ('   |--installing Unixbench on machine:%s' %machineId)
    cloudspace_publicip = str(netaddr.IPNetwork(cloudspace['publicipaddress']).ip)
    machine = pcl.actors.cloudapi.machines.get(machineId)
    account = machine['accounts'][0]

    if not j.system.net.waitConnectionTest(cloudspace_publicip, cs_publicport, 40):
        print 'Could not connect to VM over public interface'
    else:
        connection = j.remote.cuisine.connect(cloudspace_publicip, cs_publicport, account['password'], account['login'])
        connection.fabric.state.output["running"]=False
        connection.fabric.state.output["stdout"]=False
        connection.user(account['login'])
        connection.apt_get('update')
        connection.apt_get('install build-essential libx11-dev libgl1-mesa-dev libxext-dev')
        connection.run('echo %s | sudo -S wget https://storage.googleapis.com/google-code-archive-downloads/v2/'
                       'code.google.com/byte-unixbench/UnixBench5.1.3.tgz' %account['password'])
        connection.run('echo %s | sudo -S tar xvfz UnixBench5.1.3.tgz' %account['password'])
        if sendscript:
            j.do.execute('sshpass -p%s scp -o \'StrictHostKeyChecking=no\' -P %s %s  %s@%s:'
                         %(account['password'], cs_publicport, sendscript, account['login'], cloudspace_publicip))
	print('   |--finished installation on machine:%s' %machineId)
        return connection

def Run_unixbench(VM, cpu_cores, pcl, queue=None):
        machineId = VM[0]
        cloudspace_ip = VM[1]
        cloudspace_publicport = VM[2]
        machine = run_again_if_failed(pcl.actors.cloudapi.machines.get, machineId=machineId)
        account = machine['accounts'][0]
        connection = j.remote.cuisine.connect(cloudspace_ip, cloudspace_publicport, account['password'], account['login'])
        connection.fabric.state.output["running"]=False
        connection.fabric.state.output["stdout"]=False
        #change cloudscalers to account login
        print('   |--Running UnixBench on machine:%s' %machineId)
        connection.run('cd /home/cloudscalers/UnixBench; echo %s | sudo -S ./Run -c %s -i 3 > /home/cloudscalers/test_res.txt' %(account['password'],cpu_cores))
        score = connection.run('python 2_machine_script.py')
        print('   |--finished running UnixBench on machine:%s' %machineId)
        if queue:
            queue.put([machineId, score])
        score = float(score)
        return score

def results_on_csvfile(csv_file_name, Res_dir, table_string):
    #s=s1.get_string()
    result=[]
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

    with open('%s/%s.csv'%(Res_dir, csv_file_name), 'a') as outcsv:
           writer = csv.writer(outcsv)
           writer.writerows(result)

def write_onecsv_to_another(file1, csv_file_name, Res_dir):
    reader = csv.reader(open('%s/%s'%(Res_dir, file1), 'rb'))
    with open('%s/%s.csv'%(Res_dir, csv_file_name), 'a') as outcsv:
        writer = csv.writer(outcsv)
        for row in reader:
            writer.writerow(row)

#collects results in a table
def collect_results(titles, results, Res_dir, iteration=0):
    table = PrettyTable(titles)
    for i in results:
        table.add_row(i)
    table_txt = table.get_string()
    with open('%s/results.table' %Res_dir,'a') as file:
        file.write('\n%s'%table_txt)
    match = re.search('/(201.+)', Res_dir)
    results_on_csvfile(match.group(1), Res_dir, table_txt)


#utils for VM live migration test

def run_script(account, cloudspace_publicip, cloudspace_publicport, testname):
    connection = j.remote.cuisine.connect(cloudspace_publicip, cloudspace_publicport, account['password'], account['login'])
    connection.fabric.state.output["running"]=False
    connection.fabric.state.output["stdout"]=False
    connection.user(account['login'])
    connection.run('python machine_script.py %s  ' %(testname))


def check_script(account, cloudspace_publicip, cloudspace_publicport, file1, file2):
    connection = j.remote.cuisine.connect(cloudspace_publicip, cloudspace_publicport, account['password'], account['login'])
    connection.fabric.state.output["running"]=False
    connection.fabric.state.output["stdout"]=False
    connection.user(account['login'])
    return connection.run('python check_script.py %s %s ' %(file1, file2))

def writefile_on_vm(account, cloudspace_publicip, cloudspace_publicport, filename):
    connection = j.remote.cuisine.connect(cloudspace_publicip, cloudspace_publicport, account['password'], account['login'])
    connection.fabric.state.output["running"]=False
    connection.fabric.state.output["stdout"]=False
    connection.run('touch %s' %filename)
    return connection

def run_again_if_failed(func, **kwargs):
    while True:
        try:
            return func(**kwargs)
        except:
            continue
        break

#not used for now .. may be needed later
def account_vms_ovs_nodes(accountId, ccl):
    vms_ovsnodes_dict = {}
    cloudspaces = ccl.cloudspace.search({'accountId': accountId})[1:]
    for cs in cloudspaces:
        vms_per_cs = ccl.vmachine.search({'cloudspaceId': cs['id']})[1:]
        for vm in vms_per_cs:
            for disk_id in vm['disks']:
                disk = ccl.disk.search({'accountId': accountId, 'id': disk_id})[1]
                if disk['descr'] == 'Machine disk of type D':
                    ovs_ip = re.search('(\d+.){3}(\d+)', disk['referenceId'])
                    vms_ovsnodes_dict[vm['hostName']] = ovs_ip.group()
                    break
    return vms_ovsnodes_dict

def get_vm_ovs_node(vmid, ccl):
    #make sure vmid is int
    vm = ccl.vmachine.search({'id': vmid})
    for disk_id in vm['disks']:
        disk = ccl.disk.search({'id': disk_id})[1]
        if disk['descr'] == 'Machine disk of type D':
            ovs_ip = re.search('(\d+.){3}(\d+)', disk['referenceId'])
            break
    return ovs_ip


def push_results_to_repo(Res_dir, test_type=''):
    match = re.search('(/201.+)', Res_dir)
    Res_file = Res_dir + match.group(1) + '.csv'
    if j.do.exists('%s' %Res_file):
       print('Pushing resutls to the repo')
       str = j.do.execute('cd ../ && git stash')
       j.do.execute('cd ../ && git pull')
       if str[1] != 'No local changes to save\n':
            j.do.execute('cd ../ && git stash pop')
       j.do.execute('cd ../ && git add %s' %Res_file)
       if test_type =='FIO_test':
           j.do.execute('cd ../ && git add %s/Perf_parameters.cfg' %Res_dir)
       if test_type == 'demo_run_fio':
           j.do.execute('cd ../ && git add %s/Perf_parameters.cfg' %Res_dir)
           j.do.execute('cd ../ && git add %s/VMs_creation_time.csv' %Res_dir)
       if test_type == 'fio_alba':
           j.do.execute('cd ../ && git add %s/Perf_parameters.cfg' %Res_dir)
       j.do.execute('cd ../ && git commit -m \'Pushing: %s  \'' %Res_file)
       j.do.execute('cd ../ && git push')
    else:
       print('Found problems during running the test.. removing results directory..')
       j.do.execute('rm -rf %s' %Res_dir)
