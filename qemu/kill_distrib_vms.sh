#!/bin/bash

for VMID in {0..8}
do

tel="4568$VMID"
SERVER=$(($VMID/3))
HOST="v-02$SERVER"

echo "Killing on $HOST $tel"
echo 'q' | nc $HOST $tel

done
