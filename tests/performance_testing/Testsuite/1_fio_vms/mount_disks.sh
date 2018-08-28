#!/bin/bash
password=$1
disk=$2
type=$3
mountpoint=$4
pids=()
length=$(ps -ef | grep vd$disk | awk '{print $2}' | wc -l)
for pid in $(ps -ef | grep vd$disk | awk '{print $2}'); do pids+=($pid); done
for ((i=0;i<$length;i++)); do echo $password | sudo -S  kill -9 ${pids[i]}; done
sleep 1
if [ $type == filesystem ]
then
    echo $password | sudo -S umount -l /dev/vd$disk
    echo $password | sudo -S mkfs.ext4 /dev/vd$disk
    echo $password | sudo -S mkdir -p /mnt/vd$disk
    echo $password | sudo -S mount /dev/vd$disk /mnt/vd$disk -o noatime
else
    if [ $(mount | grep -c /mnt/vdb) == 1 ]
    then
        echo $password | sudo -S umount -l /dev/vd$disk;
    fi
fi
