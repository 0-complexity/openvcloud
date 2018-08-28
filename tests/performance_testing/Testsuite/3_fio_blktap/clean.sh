#!/bin/sh
pids=()
minors=()
length=$(tap-ctl list | grep pid | awk '{print $1}' | cut -d '=' -f 2 | wc -l)
for pid in $(tap-ctl list | grep pid | awk '{print $1}' | cut -d '=' -f 2); do pids+=($pid); done
for minor in $(tap-ctl list | grep pid | awk '{print $2}' | cut -d '=' -f 2); do minors+=($minor); done
for ((i=0;i<$length;i++)); do tap-ctl destroy -p ${pids[i]} -m ${minors[i]}; done

