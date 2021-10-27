#!/bin/bash

# will be using IP addr 172.29.200.161

pw='OwUser'

for base in {0..16}
do
  IP="172.29.200.16$base"
  ping $IP -q -c 1 &> /dev/null

  if [ "$?" = 0 ];
  then
    echo "Updating $IP"
    sshpass -p $pw ssh "ow@$IP" -q "docker rmi alfuerst/controller:latest"
    sshpass -p $pw ssh "ow@$IP" -q "docker rmi alfuerst/invoker:latest"

    sshpass -p $pw ssh "ow@$IP" -q "docker pull alfuerst/controller:latest"
    sshpass -p $pw ssh "ow@$IP" -q "docker pull alfuerst/invoker:latest"

    sshpass -p $pw ssh "ow@$IP" -q "cd /home/ow/openwhisk-caching; git pull"
  fi
done