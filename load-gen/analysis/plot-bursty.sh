#!/bin/bash

for ITER in 0 1 2
do

for USERS in 120 80
do

for BAL in BoundedLoadsLoadBalancer RoundRobinLB ShardingContainerPoolBalancer RandomForwardLoadBalancer RandomLoadUpdateBalancer EnhancedShardingContainerPoolBalancer
do

python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" $USERS
python3 map_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" $USERS
python3 plot_invocations.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/*/* --users $USERS
python3 latency_over_time.py --path "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" --users $USERS

done

done

done


for USERS in 120 80 # 20 50
do

python3 compare_latencies.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS
python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS
python3 plot_global_latency.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS

done

mv *pdf ./bursty
