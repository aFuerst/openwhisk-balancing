#!/bin/bash

# ../repos/qemu-5.1.0/build/qemu-img convert -O raw ow-ubu.qcow openwhisk-cache-ubu.img
# ../repos/qemu-5.1.0/build/qemu-img resize openwhisk-cache-ubu.img +16G

drive=/extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
backingdir=/extra/alfuerst/qemu-imgs/backing-files
IP=172.29.200.161
mac=06:01:02:03:04:00
# if [ "$((hostname))" -eq "v-020" ]; then
# drive=/data2/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
# backingdir=/data2/alfuerst/qemu-imgs/backing-files
# IP=172.29.200.162
# mac=06:01:02:03:04:01
# fi
# if [ "$((hostname))" -eq "v-021" ]; then
# IP=172.29.200.163
# mac=06:01:02:03:04:02
# fi

# will be using IP addr 172.29.200.161
qemu-system-x86_64 \
    -enable-kvm \
    -smp cpus=24 -cpu host \
    -m 64G \
    -daemonize \
    -nographic \
    -display none \
    -netdev bridge,id=mynet0,br=br0 \
    -device virtio-net-pci,netdev=mynet0,mac=$mac \
    -monitor telnet:127.0.0.1:45680,server,nowait \
    -drive file="$drive",if=virtio,aio=threads,format=raw \
    -debugcon file:debug.log -global isa-debugcon.iobase=0x402

# sleep 10

# pw='OwUser'

# sshpass -p $pw ssh "ow@$IP" "docker rmi alfuerst/controller:latest"
# sshpass -p $pw ssh "ow@$IP" "docker rmi alfuerst/invoker:latest"

# sshpass -p $pw ssh "ow@$IP" "docker pull alfuerst/controller:latest"
# sshpass -p $pw ssh "ow@$IP" "docker pull alfuerst/invoker:latest"

# sshpass -p $pw ssh "ow@$IP" "cd /home/ow/openwhisk-caching; git pull"

# kill VM
# echo 'q' | nc 127.0.0.1 45680

# scp /extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img v-021:/extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
# scp /extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img v-020:/data2/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
