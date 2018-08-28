#!/usr/bin/env/python
import sys
import os
import multiprocessing


def FIO_test(
    disk,
    testrun_time,
    machineId,
    account_pass,
    iteration,
    datasize_process,
    write_type,
    rwmixwrite,
    bs,
    iodepth,
    direct_io,
    rate_iops,
    numjobs,
    filesystem,
):
    if filesystem == "filesystem":
        os.system(
            "echo %s | sudo -S fio --bs=%s --iodepth=%s --direct=%s --ioengine=libaio --name=test_iter%s_vd%s --size=%sM --readwrite=%s --rwmixwrite=%s"
            " --group_reporting --directory=/mnt/vd%s --runtime=%s --output=machine%s_iter%s_%s_results/result%s_iter%s_vd%s.txt --rate_iops=%s --numjobs=%s"
            % (
                account_pass,
                bs,
                iodepth,
                direct_io,
                iteration,
                disk,
                datasize_process,
                write_type,
                rwmixwrite,
                disk,
                testrun_time,
                machineId,
                iteration,
                write_type,
                machineId,
                iteration,
                disk,
                rate_iops,
                numjobs,
            )
        )

    else:
        os.system(
            "echo %s | sudo -S fio --bs=%s --iodepth=%s --direct=%s --ioengine=libaio --name=test_iter%s_vd%s --size=%sM --readwrite=%s --rwmixwrite=%s"
            "  --group_reporting --filename=/dev/vd%s --runtime=%s --output=machine%s_iter%s_%s_results/result%s_iter%s_vd%s.txt --rate_iops=%s --numjobs=%s"
            % (
                account_pass,
                bs,
                iodepth,
                direct_io,
                iteration,
                disk,
                datasize_process,
                write_type,
                rwmixwrite,
                disk,
                testrun_time,
                machineId,
                iteration,
                write_type,
                machineId,
                iteration,
                disk,
                rate_iops,
                numjobs,
            )
        )


if __name__ == "__main__":
    testrun_time = sys.argv[1]
    machineId = sys.argv[2]
    account_pass = sys.argv[3]
    iteration = sys.argv[4]
    no_of_disks = int(sys.argv[5])
    data_size = int(sys.argv[6])
    write_type = sys.argv[7]
    bs = sys.argv[8]
    iodepth = sys.argv[9]
    direct_io = sys.argv[10]
    rwmixwrite = sys.argv[11]
    rate_iops = int(sys.argv[12])
    numjobs = int(sys.argv[13])
    filesystem = sys.argv[14]
    datasize_process = data_size / numjobs

    disk_list = ["b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    os.system(
        "mkdir base_machine%s_iter%s_%s_results" % (machineId, iteration, write_type)
    )
    if os.path.isdir(
        "machine%s_iter%s_%s_results" % (machineId, iteration, write_type)
    ):
        os.system(
            "rm -rf machine%s_iter%s_%s_results/*" % (machineId, iteration, write_type)
        )
    else:
        os.system(
            "mkdir machine%s_iter%s_%s_results" % (machineId, iteration, write_type)
        )
    processes = []
    for iter_on_disks in range(no_of_disks):
        p = multiprocessing.Process(
            target=FIO_test,
            args=(
                disk_list[iter_on_disks],
                testrun_time,
                machineId,
                account_pass,
                iteration,
                datasize_process,
                write_type,
                rwmixwrite,
                bs,
                iodepth,
                direct_io,
                rate_iops,
                numjobs,
                filesystem,
            ),
        )
        processes.append(p)
    for j in range(no_of_disks):
        processes[j].start()
        # print('FIO testing has been started on machine: %s and on disk: vd%s'% (machineId, disk_list[j]))
    while any(p.is_alive() == True for p in processes):
        os.system(
            "sar -r 1 1 >> base_machine%s_iter%s_%s_results/memory_usage.txt"
            % (machineId, iteration, write_type)
        )
        os.system(
            "mpstat -P ALL >> base_machine%s_iter%s_%s_results/cpuload.txt"
            % (machineId, iteration, write_type)
        )
    for k in range(no_of_disks):
        processes[k].join()
        # print('FIO testing has been ended on machine: %s and on disk: vd%s'% (machineId, disk_list[k]))
    os.system(
        "cp -r base_machine%s_iter%s_%s_results/* machine%s_iter%s_%s_results/"
        % (machineId, iteration, write_type, machineId, iteration, write_type)
    )
    os.system(
        "rm -rf base_machine%s_iter%s_%s_results" % (machineId, iteration, write_type)
    )
