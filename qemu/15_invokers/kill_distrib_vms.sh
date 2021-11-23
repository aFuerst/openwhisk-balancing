#!/bin/bash

for VMID in {0..15}
do

tel=":4568$VMID"
if [ $VMID -gt 9 ];
then
tel=":456$VMID"
fi

SERVER=0
if [ $VMID -lt 4 ]; then
SERVER=2
elif [ $VMID -lt 10 ]; then
SERVER=1
fi


HOST="v-02$SERVER"

echo "Killing on $HOST $tel"
echo 'q' | nc $HOST $tel

done
