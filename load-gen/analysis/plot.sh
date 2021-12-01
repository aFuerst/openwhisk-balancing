#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 50 70
do

for BAL in BoundedLoadsLoadBalancer RoundRobinLB ShardingContainerPoolBalancer RandomForwardLoadBalancer
do

python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/" $USERS
# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/$USERS*png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/$USERS-$BAL/"

done

python3 compare_function.py "/extra/alfuerst/openwhisk-logs/30min-compare/$ITER/" $USERS

done

cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/50-*compare*.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/
cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/70-*compare*.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/

done

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users 30
python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users 50
python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users 70

cp *invokes.png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/"


cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-RandomForwardLoadBalancer/50-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-RandomForwardLoadBalancer-loadAvg.png
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-RandomForwardLoadBalancer/70-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-RandomForwardLoadBalancer-loadAvg.png

cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-ShardingContainerPoolBalancer/50-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-ShardingContainerPoolBalancer-loadAvg.png
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-ShardingContainerPoolBalancer/70-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-ShardingContainerPoolBalancer-loadAvg.png

for USERS in 50 70
do

python3 compare_latencies.py --path /extra/alfuerst/vary-ceil-30min/*/*/*/ --users $USERS
python3 plot_tputs.py --path /extra/alfuerst/vary-ceil-30min/*/*/*/ --users $USERS

done

cp *compare-overload*png "/home/alfuerst/repos/faaslb-osdi22/figs/overload-compare/"

