**3_fio_blktap** is an **internal** test, so only documented here below.


# FIO_blktap test purpose:
 RUN FIO on some blktap devices (disks) on which their raw files on the fuse file system (/mnt/vmstor/)
 and calculate the IOPS to be able to compare it with the fio_test that runs on the top of the vms so we
 can know how much loss due to QEMU and compare it with alba as well to figure out the loss due to the edge

# Running the test
1- clone the repo on any cpu node
2- cd G8_testing/performance_testing
3- vim Testsuite/3_fio_blktap/Perf_parameters.cfg (for changing parameters as needed)
4- jspython Testsuite/3_fio_blktap/blktap.py
5- The test will clean itself after finishing


# Check the test results
- The results of the tests can be viewed in the following directory:

  ```
  cd G8_testing/tests_results/fio_blktap/(date)_(cpu_name).(env_name)_testresults(run_number)/
  vim (date)_(cpu_name).(env_name)_testresults(run_number).csv
  ```

- For each of the results there is also a copy available of the used **Perf_parameters.cfg** file:
    - Make sure to change ovs nodes ips and their number as well

  ```
  vim /G8_testing/tests_results/fio_blktap/(date)_(cpu_name).(env_name)_testresults(run_number)/Perf_parameters.cfg
  ```
- Results sample for 2 disks:
+------------+-------+
|   Disks    |  IOPS |
+------------+-------+
|   disk_1   |  6971 |
|   disk_2   |  7012 |
| Total_IOPS | 13983 |
+------------+-------+
