#!/bin/bash

ready_vm () {
timeout 120 sshpass -p $1 ssh $2 "docker rm -f \$(docker ps -aq)" &> /dev/null
}

export HOST=https://172.29.200.161:10001
export AUTH=5e9fb463-3082-4fce-847b-dbc17a7fbfa0:AZcoEhmD4dMsFTu7SPOAI4NkyDqtyaqkbxyud5bnMW5MssmPtQoC9BggNweGcJIj

for USERS in {20..120..10}
do

MEMORY="32G"
IMAGE="alfuerst"
LOADSTRAT="LoadAvg"
ALGO="RandomForward"
OUTPTH="/out/path/name.csv"
BALANCER="ShardingContainerPoolBalancer"
# RoundRobinLB
EVICTION="GD"
ENVIRONMENT="host-distrib"
boundedceil="1.5"

whisk_logs_dir=/home/ow/openwhisk-logs
redisPass='OpenWhisk'
redisPort=6379
ansible=/home/ow/openwhisk-balancing/ansible

r=5
warmup=$(($USERS/$r))
echo "users: $USERS; warmup seconds: $warmup"
BASEPATH="/extra/alfuerst/openwhisk-logs-two/"
pth="$BASEPATH/findload/$USERS-$BALANCER"
mkdir -p $pth
user='ow'
pw='OwUser'

if [ -f "$pth/controller0_logs.log" ]; then
echo "skipping run $pth"
python3 locust_parse.py "$pth/logs_transactions.csv"
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
echo "docker rm exit code: $code"
if [ $code != "0" ]; then
  echo "having to reboot VMs"

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

    echo "rebooting on $VM_HOST $tel"
    echo 'system_reset' | nc $VM_HOST $tel


  done
  sleep 30
fi
#####################################

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; 
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass;
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=16 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.2 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=$boundedceil -e invoker_eviction_strategy=$EVICTION -e controller_loadbalancer_spi=org.apache.openwhisk.core.loadBalancer.$BALANCER -e controller_horizscale=false -e invoker_idle_container=60minutes -e invoker_container_network_name=host -e invoker_pause_grace=60minutes"
ANSIBLE_HOST="$user@172.29.200.161"
sshpass -p $pw ssh $ANSIBLE_HOST "$cmd" &> "$pth/logs.txt"

locust --headless --users $USERS -r $r -f locustfile-transaction.py --csv "$pth/logs" --log-transactions-in-file --run-time 10m &>> "$pth/logs.txt"
python3 locust_parse.py "$pth/logs_transactions.csv"

DEST=$pth

sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" $DEST
sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/nginx/nginx_access.log" $DEST

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
  sshpass -p $pw scp "$user@$IP:$log_pth" $DEST

  done

python3 ../analysis/plot_invoker_load.py $pth $USERS
# python3 ../analysis/plot_invocations.py $pth $USERS
# python3 ../analysis/map_invocation_to_load.py $pth $USERS
done
# done
