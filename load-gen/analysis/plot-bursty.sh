#!/bin/bash

for ITER in 0 1 2 3
do

python3 paper/plot_loadbalance_variance.py --path /extra/alfuerst/openwhisk-logs-two/bursty/$ITER/*/ --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl-bursty/$ITER/* --users 120 --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
cp /extra/alfuerst/openwhisk-logs-two/bursty/$ITER/120-loadAvg-variance.pdf ./bursty/$ITER-120-loadAvg-variance.pdf

for USERS in 120 # 80
do

for BAL in RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
do

python3 map_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" $USERS &
python3 scatter_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" $USERS &
python3 latency_over_time.py --path "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" --users $USERS &
python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs-two/bursty/$ITER/$USERS-$BAL/" $USERS &

done

done

done

cp /extra/alfuerst/openwhisk-logs-two/bursty/0/120-ShardingContainerPoolBalancer/120-loadAvg.pdf ./bursty/ShardingContainerPoolBalancer-120-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs-two/bursty/0/120-RLULFSharding/120-loadAvg.pdf ./bursty/RLULFSharding-120-loadAvg.pdf

for USERS in 120
do

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer &
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS &
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS --global &
python3 plot_invocations.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/*/* --users $USERS &
python3 compare_latencies.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/*/* --users $USERS --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl-bursty/*/* --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer &
python3 plot_global_latency.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --users $USERS --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl-bursty/*/* --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer &
python3 plot_tputs_ttl.py --path /extra/alfuerst/openwhisk-logs-two/bursty/*/* --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl-bursty/*/* --users $USERS --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer --loc 'upper left'

done

wait $(jobs -p)
mv *pdf ./bursty
cp ./bursty/* /home/alfuerst/repos/faaslb-osdi22/figs/bursty
