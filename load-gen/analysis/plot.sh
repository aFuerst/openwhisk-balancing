#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 20 120
do

python3 paper/plot_loadbalance_variance.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/*/ --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl/$ITER/* --users $USERS --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
cp /extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/$USERS-loadAvg-variance.pdf ./compare/$ITER-$USERS-loadAvg-variance.pdf

for BAL in RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
do

python3 map_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/$USERS-$BAL/" $USERS &
python3 scatter_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/$USERS-$BAL/" $USERS &
python3 latency_over_time.py --path "/extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/$USERS-$BAL/" --users $USERS &
python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs-two/30min-compare/$ITER/$USERS-$BAL/" $USERS &

done

done

done

cp /extra/alfuerst/openwhisk-logs-two/30min-compare/2/120-ShardingContainerPoolBalancer/120-loadAvg.pdf ./compare/ShardingContainerPoolBalancer-120-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs-two/30min-compare/2/120-RLULFSharding/120-loadAvg.pdf ./compare/RLULFSharding-120-loadAvg.pdf

cp /extra/alfuerst/openwhisk-logs-two/30min-compare/1/20-ShardingContainerPoolBalancer/20-loadAvg.pdf ./compare/ShardingContainerPoolBalancer-20-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs-two/30min-compare/1/20-RLULFSharding/20-loadAvg.pdf ./compare/RLULFSharding-20-loadAvg.pdf

for USERS in 20 120
do

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/* --users $USERS --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer &
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/* --users $USERS &
python3 plot_invocations.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/*/* --users $USERS &
python3 plot_global_latency.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/* --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl/*/* --users $USERS --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer &

done

python3 plot_tputs_ttl.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/* --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl/*/* --users 20 --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer
python3 plot_tputs_ttl.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/* --ttl /extra/alfuerst/openwhisk-logs-two/30min-compare-ttl/*/* --users 120 --balancers RLULFSharding ShardingContainerPoolBalancer LeastLoadBalancer BoundedLoadsLoadBalancer --loc 'upper left'
# python3 compare_latencies.py --path /extra/alfuerst/openwhisk-logs-two/30min-compare/*/*/* --users $USERS
wait $(jobs -p)
mv *.pdf ./compare
cp ./compare/* /home/alfuerst/repos/faaslb-osdi22/figs/compare