#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=036c13e2-c941-45b2-88eb-6c6f71bb9403:qtEgqx6xwz0n4IH4hb8ydoA2H48O9rxYmUgyj6vBNAdjBNnDnfr1Bjfg0ciCrPGi

USERS=100
for USERS in {100..500..50}
do

MEMORY="40G"
IMAGE="whisk"
LOADSTRAT="LoadAvg"
ALGO="Sharding"
OUTPTH="/out/path/name.csv"
BALANCER="ShardingContainerPoolBalancer"
EVICTION="GD"
ENVIRONMENT="host-distrib"

whisk_logs_dir=/home/ow/openwhisk-logs
redisPass='OpenWhisk'
redisPort=6379
ansible=/home/ow/openwhisk-caching/ansible

r=20
warmup=$(($USERS/$r))
echo "users: $USERS; warmup seconds: $warmup"
pth="vary_users/original-sharding/$USERS-users"
mkdir -p $pth
user='ow'
pw='OwUser'

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; 
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass;
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=8 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.5 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=1.2 -e invoker_eviction_strategy=$EVICTION -e controller_loadbalancer_spi=org.apache.openwhisk.core.loadBalancer.$BALANCER"
ANSIBLE_HOST="$user@172.29.200.161"
sshpass -p $pw ssh $ANSIBLE_HOST "$cmd" &> "$pth/logs.txt"

# if [ $? != 0 ]; then
# return
# do

locust --headless --users $USERS -r $r -f locustfile-transaction.py --csv "$pth/logs" --log-transactions-in-file --run-time 10m &>> "$pth/logs.txt"
python3 locust_parse.py "$pth/logs_transactions.csv"

DEST=$pth



sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" $DEST
sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/nginx/nginx_access.log" $DEST


  for VMID in {1..8}
  do

  INVOKERID=$(($VMID-1))
  # IP=$(($VMID+1))
  IP="172.29.200.$((161 + $base))"

  name="invoker$INVOKERID"
  pth="/home/ow/openwhisk-logs/wsklogs/"
  pth+="$name/"
  pth+="$name"
  pth+="_logs.log"
  sshpass -p $pw scp "$user@$IP:$pth" $DEST

  done
python3 ../analysis/plot_invoker_load.py $DEST $USERS
python3 ../analysis/plot_invocations.py $DEST $USERS
python3 ../analysis/map_invocation_to_load.py $DEST $USERS
done
# done