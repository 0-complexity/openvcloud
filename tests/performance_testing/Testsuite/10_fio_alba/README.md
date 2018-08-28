**10_fio_alba** is an **internal** test, so only documented here below.

This test is designed to run from an Open vStorage node, and requires the Fargo release
# Alba test Purpose:
 RUN FIO on some raw files (disks) on the fuse file systems(/mnt/vmstor/ ) and calculate the IOPS to be
 able to compare it with the fio_test that runs on the top of the vms so we measure how much
 loss in between

# Running the test
1- clone the repo on any ovs node
2- cd G8_testing/performance_testing
3- vim Testsuite/10_fio_alba/Perf_parameters.cfg (for changing parameters as needed)
4- jspython Testsuite/10_fio_alba/fio_alba.py
5- The test will clean itself after finishing


# Check the test results
- The results of the tests can be viewed in the following directory:

  ```
  cd G8_testing/tests_results/alba/(date)_(cpu_name).(env_name)_testresults(run_number)/
  vim (date)_(cpu_name).(env_name)_testresults(run_number).csv
  ```

- For each of the results there is also a copy available of the used **Perf_parameters.cfg** file:

  ```
  vim /G8_testing/tests_results/FIO_test/(date)_(cpu_name).(env_name)_testresults(run_number)/Perf_parameters.cfg
  ```
- Results sample for 3 disks:
+------------+---------+
|   Disks    |   IOPS  |
+------------+---------+
|   disk_1   | 1060900 |
|   disk_2   | 1046800 |
|   disk_3   |  87477  |
| Total_IOPS | 2195177 |
+------------+---------+
