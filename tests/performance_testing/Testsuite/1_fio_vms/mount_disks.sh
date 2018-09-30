#!/bin/bash
set -e
password=$1
disk=$2
type=$3
oldmount=$(mount | grep -E "vdb|vdb1" | awk '{print $1}')
if [ -z $oldmount ]
then
echo $password |sudo -S  dd if=/dev/zero of=/dev/vd$disk bs=512 count=1000
else
echo $password | sudo -S umount -l $oldmount

fi 
if [ $type == filesystem ]
then
    echo $password | sudo -S parted -s /dev/vd$disk mklabel gpt
    echo $password | sudo -S parted -s /dev/vd$disk mkpart pftest  0% 100%
    echo $password | sudo -S mkfs.ext4 -F  /dev/vd$disk$((1))
if  [ ! -d /mnt/vd$disk$((1)) ] 
then
    echo $password | sudo -S mkdir -p /mnt/vd$disk$((1))
    echo $password | sudo -S mount /dev/vd$disk$((1)) /mnt/vd$disk$((1)) -o noatime
else
echo $password | sudo -S mount /dev/vd$disk$((1)) /mnt/vd$disk$((1)) -o noatime
fi
else

exit

fi
