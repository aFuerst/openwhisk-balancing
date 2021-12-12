#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 20 50 70
do

for BAL in BoundedLoadsLoadBalancer RoundRobinLB ShardingContainerPoolBalancer RandomForwardLoadBalancer RandomLoadUpdateBalancer
do

python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/" $USERS &
python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/bursty-2/$ITER/$USERS-$BAL/" $USERS
# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/$USERS*pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/$USERS-$BAL/"

done

done

# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/50-*compare*.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/
# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/70-*compare*.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/

done

cp /extra/alfuerst/openwhisk-logs/30min-compare/1/30-RandomForwardLoadBalancer/30-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/30-RandomForwardLoadBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-RandomForwardLoadBalancer/50-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-RandomForwardLoadBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-RandomForwardLoadBalancer/70-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-RandomForwardLoadBalancer-loadAvg.pdf

cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-RandomLoadUpdateBalancer/50-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-RandomLoadUpdateBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/30-RandomLoadUpdateBalancer/30-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/30-RandomLoadUpdateBalancer-loadAvg.pdf

cp /extra/alfuerst/openwhisk-logs/30min-compare/0/20-RandomForwardLoadBalancer/20-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/20-RandomForwardLoadBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/0/20-RandomLoadUpdateBalancer/20-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/20-RandomLoadUpdateBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/0/20-ShardingContainerPoolBalancer/20-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/20-ShardingContainerPoolBalancer-loadAvg.pdf

cp /extra/alfuerst/openwhisk-logs/30min-compare/1/30-ShardingContainerPoolBalancer/30-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/30-ShardingContainerPoolBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-ShardingContainerPoolBalancer/50-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-ShardingContainerPoolBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-ShardingContainerPoolBalancer/70-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-ShardingContainerPoolBalancer-loadAvg.pdf

for USERS in 20 30 50 70
do

python3 compare_latencies.py --path /extra/alfuerst/vary-ceil-30min/*/*/* --users $USERS
python3 plot_tputs.py --path /extra/alfuerst/vary-ceil-30min/*/*/* --users $USERS --ceil

mv *invokes-ceil.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/overload-compare/"
mv *compare-overload*pdf "/home/alfuerst/repos/faaslb-osdi22/figs/overload-compare/"

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users $USERS

mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/"
mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/"

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/bursty-2/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/bursty-2/*/* --users $USERS

mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"
mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"

done

