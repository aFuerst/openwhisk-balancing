#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=5973c02d-4c68-4b6d-af13-17f9e3e82028:ezIS6fF9BREmaMLGZrVDT7Y3SauPQdt7u1rNsDnHhUPweeC186J0OePoe1kabdh4

for CEIL in 1.0 1.3 1.5 1.7 2.0
do

for USERS in 30 50 70
do

for ITERATION in {0..2}
do

BALANCER=RandomForwardLoadBalancer

MEMORY="10G"
IMAGE="alfuerst"
LOADSTRAT="LoadAvg"
EVICTION="GD"
ENVIRONMENT="host-distrib"

whisk_logs_dir=/home/ow/openwhisk-logs
redisPass='OpenWhisk'
redisPort=6379
ansible=/home/ow/openwhisk-balancing/ansible

BASEPATH="/extra/alfuerst/vary-ceil-30min/$ITERATION/compare-$CEIL"

r=5
warmup=$(($USERS/$r))
echo "$BALANCER, ceil: $CEIL; users: $USERS; warmup seconds: $warmup"
pth="$BASEPATH/$USERS-$BALANCER"
mkdir -p $pth
user='ow'
pw='OwUser'

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; 
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean;
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass;
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=4 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.2 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_loadbalancer_invoker_boundedceil=$CEIL -e invoker_eviction_strategy=$EVICTION -e controller_loadbalancer_spi=org.apache.openwhisk.core.loadBalancer.$BALANCER -e controller_horizscale=false -e invoker_idle_container=60minutes"
ANSIBLE_HOST="$user@172.29.200.161"
sshpass -p $pw ssh $ANSIBLE_HOST "$cmd" &> "$pth/logs.txt"


locust --headless --users $USERS -r $r -f locustfile-transaction.py --csv "$pth/logs" --log-transactions-in-file --run-time 30m &>> "$pth/logs.txt"
python3 locust_parse.py "$pth/logs_transactions.csv"

sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" $pth
sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/nginx/nginx_access.log" $pth


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
  sshpass -p $pw scp "$user@$IP:$log_pth" $pth

  done

python3 ../analysis/plot_invoker_load.py $pth $USERS
python3 ../analysis/plot_invocations.py $pth $USERS
python3 ../analysis/map_invocation_to_load.py $pth $USERS
python3 ../analysis/plot_latencies.py $pth $USERS
done

done

done

# for USERS in 50 60 70
# do
# python3 ../analysis/compare_latencies.py --path "vary-ceil/compare-1.0/$USERS-RandomForwardLoadBalancer/" "vary-ceil/compare-1.5/$USERS-RandomForwardLoadBalancer/" "vary-ceil/compare-2.0/$USERS-RandomForwardLoadBalancer/" --users $USERS
# done
