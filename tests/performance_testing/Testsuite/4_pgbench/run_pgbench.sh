#!/bin/bash
password=$1
disk=$2
scalefactor=$3
testruntime=$4
threadcount=$5
clientclount=$6

{

# Stop postgresql
while pgrep postgres
do
  echo $password | sudo -S service postgresql stop
  echo $password | sudo -S pkill -9 postgres
done

# Create a new data_directory
echo $password | sudo -S umount /dev/$disk
echo $password | sudo -S mkfs.ext4 /dev/$disk
if [ ! -d "/mnt/$disk" ]; then
    echo $password | sudo -S mkdir /mnt/$disk
fi
echo $password | sudo -S mount /dev/$disk /mnt/$disk
echo $password | sudo -S chown -R postgres:postgres /mnt/$disk
echo $password | sudo -S sed -i -e "s/data_directory = '.*'/data_directory = '\/mnt\/$disk'/g" /etc/postgresql/9.5/main/postgresql.conf
echo $password | sudo -S rm -rf /mnt/$disk/*
echo $password | sudo -S su postgres -c "/usr/lib/postgresql/9.5/bin/initdb /mnt/$disk"

# Start postgresql
echo $password | sudo -S service postgresql start
sleep 5

# Create database
echo $password | sudo -S su postgres -c "psql -c 'create database test;'"

# Record disk stats
start=`cat /sys/block/$disk/stat`
starttime=`date +%s`

# Run test
echo $password | sudo -S su postgres -c "pgbench -i -s $scalefactor test"
echo $password | sudo -S su postgres -c "pgbench -T $testruntime -j $threadcount -c $clientclount test"

# Record disk stats
end=`cat /sys/block/$disk/stat`
endtime=`date +%s`

} &> /dev/null

# Calculate results
read -r -a start <<< "$start"
read -r -a end <<< "$end"
seconds=$(($endtime - $starttime))
if [ "0" != "$seconds" ]; then
   echo $(((${end[2]} - ${start[2]} + ${end[6]} - ${start[6]})/($seconds)))
else
   echo 0
fi
