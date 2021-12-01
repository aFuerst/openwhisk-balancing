#!/bin/bash

# ../repos/qemu-5.1.0/build/qemu-img convert -O raw ow-ubu.qcow openwhisk-cache-ubu.img
# ../repos/qemu-5.1.0/build/qemu-img resize openwhisk-cache-ubu.img +16G

drive=/extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
backingdir=/extra/alfuerst/qemu-imgs/backing-files
user='ow'
pw='OwUser'

# will be using IP addr 172.29.200.161-8
for VMID in {0..8}
do

mac="06:01:02:03:04:0$VMID"
tel=":4568$VMID"
if [ $VMID -gt 9 ];
then
tel=":456$VMID"
fi

SERVER=2
if [ $VMID -lt 3 ]; then
SERVER=0
elif [ $VMID -lt 6 ]; then
SERVER=1
fi
debug="debug-$VMID.log"
net="mynet$VMID"

CPUS=4
if [ $VMID == 0 ]
then
CPUS=12
fi

drive=/extra/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
backingdir=/extra/alfuerst/qemu-imgs/backing-files
if [ $SERVER == 0 ]
then
drive=/data2/alfuerst/qemu-imgs/openwhisk-cache-ubu.img
backingdir=/data2/alfuerst/qemu-imgs/backing-files
fi
guestimg="$backingdir/openwhisk-guest-$VMID.qcow2"

cmd="
mkdir -p $backingdir;
rm -rf $guestimg;
qemu-img create -f qcow2 \
                -o backing_file=$drive \
                $guestimg;

sudo qemu-system-x86_64 \
    -enable-kvm \
    -smp cpus=$CPUS -cpu host \
    -m 50G \
    -daemonize \
    -nographic \
    -display none \
    -monitor  telnet:$tel,server,nowait \
    -netdev bridge,id=$net,br=br0 \
    -device virtio-net-pci,netdev=$net,mac=$mac \
    -drive file="$guestimg",if=virtio,aio=threads,format=qcow2 \
    -debugcon file:$debug -global isa-debugcon.iobase=0x402
"

HOST="v-02$SERVER"

echo "Launching on $HOST"
echo $cmd


# HOST="172.29.200.16$VMID"

ssh -i ~/.ssh/internal_rsa $HOST "$cmd"

echo ""

done
