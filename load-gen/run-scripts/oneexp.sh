#!/bin/bash

MEMORY="10G"
IMAGE="alfuerst"
LOADSTRAT="LoadAvg"
ALGO="ConsistentCache"
OUTPTH="/out/path/name.csv"
BALANCER="ConsistentCacheLoadBalancer"
EVICTION="GD"

whisk_logs_dir=/home/ow/openwhisk-logs
ENVIRONMENT=bal-distrib
redisPass='OpenWhisk'
redisPort=6379

USERS=4
LEN=10
CPUS=4

POSITIONAL=()
while [[ $# -gt 0 ]]; do
  key="$1"

  case $key in
    -m|--memory)
      MEMORY="$2"
      shift # past argument
      shift # past value
      ;;
    -l|--loadstrat)
      LOADSTRAT="$2"
      shift # past argument
      shift # past value
      ;;
    -a|--algorithm)
      ALGO="$2"
      shift # past argument
      shift # past value
      ;;
    -i|--image)
      IMAGE="$2"
      shift # past argument
      shift # past value
      ;;
    -o|--output)
      OUTPTH="$2"
      shift # past argument
      shift # past value
      ;;
    -u|--users)
      USERS="$2"
      shift # past argument
      shift # past value
      ;;
    -c|--cpus)
      CPUS="$2"
      shift # past argument
      shift # past value
      ;;
    -t|--lenmins)
      LEN="$2"
      shift # past argument
      shift # past value
      ;;
    -b|--balancer)
      BALANCER="$2"
      shift # past argument
      shift # past value
      ;;
    -e|--evict)
      EVICTION="$2"
      shift # past argument
      shift # past value
      ;;
    *)    # unknown option
      POSITIONAL+=("$1") # save it in an array for later
      shift # past argument
      ;;
  esac
done

BALANCER="org.apache.openwhisk.core.loadBalancer.$BALANCER"
ansible=/home/ow/openwhisk-caching/ansible

# props="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT properties.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=6 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=2 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=1.2"
# sshpass -p $pw ssh $HOST "$props"

cmd="cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=$IMAGE -e invoker_user_memory=$MEMORY -e controller_loadbalancer_invoker_cores=8 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=1.5 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy=$LOADSTRAT -e controller_algorithm=$ALGO -e controller_loadbalancer_invoker_boundedceil=1.2 -e invoker_eviction_strategy=$EVICTION"

user='ow'
pw='OwUser'
HOST="$user@172.29.200.161"

echo "Invoking command to clean and restart OW:"
echo "$cmd"

sshpass -p $pw ssh $HOST "cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean"

sshpass -p $pw ssh $HOST "cd $ansible; echo $ENVIRONMENT; export OPENWHISK_TMP_DIR=$whisk_logs_dir; ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass"

sshpass -p $pw ssh $HOST "$cmd"

/home/alfuerst/.pyenv/versions/3.8.2/bin/python3 ../load/ColdLoad.py --savepth $OUTPTH --numcpus $CPUS --lenmins $LEN
# t_str="$LEN"
# t_str+="m"
# /home/alfuerst/.pyenv/versions/3.8.2/bin/locust -f ../load/locustfile.py --headless --csv $OUTPTH --users $USERS -t $t_str --spawn-rate 3
