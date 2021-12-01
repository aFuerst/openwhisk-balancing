#!/bin/bash

for VMID in {0..8}
do

tel="4568$VMID"
if [ $VMID -gt 9 ];
then
tel="456$VMID"
fi

SERVER=2
if [ $VMID -lt 3 ]; then
SERVER=0
elif [ $VMID -lt 6 ]; then
SERVER=1
fi

HOST="v-02$SERVER"

echo "Killing on $HOST $tel"
echo 'q' | nc $HOST $tel

done
