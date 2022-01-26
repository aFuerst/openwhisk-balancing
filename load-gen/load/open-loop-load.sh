#!/bin/bash

ready_vm () {
timeout 120 sshpass -p $1 ssh $2 "docker rm -f \$(docker ps -aq)" &> /dev/null
}


export HOST=https://172.29.200.161:10001
export AUTH=5e9fb463-3082-4fce-847b-dbc17a7fbfa0:AZcoEhmD4dMsFTu7SPOAI4NkyDqtyaqkbxyud5bnMW5MssmPtQoC9BggNweGcJIj

for ITER in {0..3}
do

for BALANCER in RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
do

boundedceil="6"
if [ "$BALANCER" = "BoundedLoadsLoadBalancer" ]; then
boundedceil="4"
fi

MEMORY="32G"
IMAGE="alfuerst"
LOADSTRAT="LoadAvg"
ALGO="RandomForward"
OUTPTH="/out/path/name.csv"
EVICTION="GD"
ENVIRONMENT="host-distrib"

whisk_logs_dir=/home/ow/openwhisk-logs
redisPass='OpenWhisk'
redisPort=6379
ansible=/home/ow/openwhisk-balancing/ansible

BASEPATH="/extra/alfuerst/openwhisk-logs-two/openload/$ITER/$BALANCER"

echo "balancer=$BALANCER; iter $ITER"
mkdir -p $BASEPATH
user='ow'
pw='OwUser'

if [ -f "$BASEPATH/data.pckl" ]; then
continue
fi

#####################################
# ansible can get stuck trying to clear docker containers on invokers. do it manually with reboot if tineout occurs
for VMID in {1..8}
do
INVOKERID=$(($VMID-1))
# IP=$(($VMID+1))
IP="172.29.200.$((161 + $VMID))"
ready_vm $pw "$user@$IP" &

done

wait $(jobs -p)

code="$?"
if [ $code != "0" ]; then
  echo "docker rm exit code: $code ; having to reboot VMs"

  for VMID in {1..8}
  do

    # reboot VMs
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

    VM_HOST="v-02$SERVER"

    echo 'system_reset' | nc $VM_HOST $tel  > /dev/null


  done
  sleep 30
fi
#####################################

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; 
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass;
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=16 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.0 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=$boundedceil -e invoker_eviction_strategy=$EVICTION -e controller_loadbalancer_spi=org.apache.openwhisk.core.loadBalancer.$BALANCER -e controller_horizscale=false -e invoker_idle_container=60minutes -e invoker_container_network_name=host -e invoker_pause_grace=60minutes"
ANSIBLE_HOST="$user@172.29.200.161"
sshpass -p $pw ssh $ANSIBLE_HOST "$cmd" &> "$BASEPATH/logs.txt"

python3 OpenLoad.py --savepth $BASEPATH --numcpus 16 --lenmins 30 --host $HOST --auth $AUTH &> "$BASEPATH/run.log"

sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" $BASEPATH
sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/nginx/nginx_access.log" $BASEPATH

  for VMID in {1..8}
  do

  INVOKERID=$(($VMID-1))
  # IP=$(($VMID+1))
  IP="172.29.200.$((161 + $VMID))"

  name="invoker$INVOKERID"
  log_pth="/home/ow/openwhisk-logs/wsklogs/"
  log_pth+="$name/"
  log_pth+="$name"
  log_pth+="_logs.log"
  sshpass -p $pw scp "$user@$IP:$log_pth" $BASEPATH

  done

done
done