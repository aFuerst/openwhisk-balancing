#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=e0ddac86-ac5a-45e0-bf37-ec3dcf3f70de:WwX7nwMvLWHQhW2vjZtyZkL8QVTcKa4PplCp2riFYn49TnBogJb21V09EcEzIw2D

USERS=100
for USERS in {100..1000..100}
do

MEMORY="40G"
IMAGE="alfuerst"
LOADSTRAT="LoadAvg"
ALGO="ConsistentCache"
OUTPTH="/out/path/name.csv"
BALANCER="ConsistentCacheLoadBalancer"
EVICTION="GD"
ENVIRONMENT="host-distrib"

whisk_logs_dir=/home/ow/openwhisk-logs
ENVIRONMENT=bal-distrib
redisPass='OpenWhisk'
redisPort=6379

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=8 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.5 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=1.2 -e invoker_eviction_strategy=$EVICTION"
HOST="$user@172.29.200.161"
sshpass -p $pw ssh $HOST "cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean" > /dev/null
sshpass -p $pw ssh $HOST "cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass" > /dev/null
sshpass -p $pw ssh $HOST "$cmd"  > /dev/null

echo "users: $USERS"
r=$((USERS/10))
pth="testlocust/cache-$USERS-users"
mkdir -p $pth
locust --headless --users $USERS -r $r -f locustfile-transaction.py --csv "$pth/logs" --log-transactions-in-file --run-time 10m &> "$pth/logs.txt"
python3 locust_parse.py "$pth/logs_transactions.csv"

done

DEST=$pth

user='ow'
pw='OwUser'

sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" $DEST
sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/nginx/nginx_access.log" $DEST


for VMID in {1..8}
do

INVOKERID=$(($VMID-1))
IP=$(($VMID+1))

name="invoker$INVOKERID"
pth="/home/ow/openwhisk-logs/wsklogs/"
pth+="$name/"
pth+="$name"
pth+="_logs.log"
sshpass -p $pw scp "$user@172.29.200.16$IP:$pth" $DEST

done

# done