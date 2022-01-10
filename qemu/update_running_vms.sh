#!/bin/bash

# will be using IP addr 172.29.200.161

pw='OwUser'

for base in {0..15}
do
  IP="172.29.200.$((161 + $base))"
  ping $IP -q -c 1 &> /dev/null

  if [ "$?" = 0 ];
  then
    echo "Updating $IP"
    cmd="#docker kill \$(docker ps -q);
# docker rm -f \$(docker ps -aq);
# docker system prune -f;
# docker rmi alfuerst/controller:latest;
# docker rmi alfuerst/invoker:latest;"
    cmd="docker pull v-019.victor.futuresystems.org:5000/alfuerst/controller:latest;
docker pull v-019.victor.futuresystems.org:5000/alfuerst/invoker:latest;
docker pull alfuerst/controller:latest;
docker pull alfuerst/invoker:latest;
docker pull alfuerst/action-python-v3.7;
docker pull alfuerst/action-python-v3.9;
docker pull alfuerst/action-python-v3.6-ai;
cd /home/ow/openwhisk-balancing;
git pull"

    sshpass -p $pw ssh "ow@$IP" -q $cmd & > /dev/null
    # sshpass -p $pw ssh "ow@$IP" -q "docker kill $(docker ps -q)"
    # sshpass -p $pw ssh "ow@$IP" -q "docker rm -f $(docker ps -aq)"
    # sshpass -p $pw ssh "ow@$IP" -q "docker system prune -f"

    # sshpass -p $pw ssh "ow@$IP" -q "docker rmi alfuerst/controller:latest"
    # sshpass -p $pw ssh "ow@$IP" -q "docker rmi alfuerst/invoker:latest"

    # sshpass -p $pw ssh "ow@$IP" -q "docker pull alfuerst/controller:latest"
    # sshpass -p $pw ssh "ow@$IP" -q "docker pull alfuerst/invoker:latest"

    # sshpass -p $pw ssh "ow@$IP" -q "cd /home/ow/openwhisk-balancing; git pull"
  fi
done