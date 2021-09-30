#!/bin/bash

# ../repos/qemu-5.1.0/build/qemu-img convert -O raw ow-ubu.qcow openwhisk-cache-ubu.img
# ../repos/qemu-5.1.0/build/qemu-img resize openwhisk-cache-ubu.img +16G

cd=ubuntu-20.10-live-server-amd64.iso
drive=/extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
backingdir=/extra/alfuerst/qemu-imgs/backing-files

# will be using IP addr 172.29.200.161
qemu-system-x86_64 \
    -enable-kvm \
    -smp cpus=24 -cpu host \
    -m 64G \
    -daemonize \
    -nographic \
    -display none \
    -netdev bridge,id=mynet0,br=br0 \
    -device virtio-net-pci,netdev=mynet0,mac=06:01:02:03:04:00 \
    -monitor telnet:127.0.0.1:45682,server,nowait \
    -drive file="$drive",if=virtio,aio=threads,format=raw \
    -debugcon file:debug.log -global isa-debugcon.iobase=0x402
