#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 50 70
do

for BAL in BoundedLoadsLoadBalancer RoundRobinLB ShardingContainerPoolBalancer RandomForwardLoadBalancer
do

python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/" $USERS &
python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/bursty/$ITER/$USERS-$BAL/" $USERS &
# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/$USERS-$BAL/$USERS*png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/$USERS-$BAL/"

done

done

# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/50-*compare*.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/
# cp /extra/alfuerst/openwhisk-logs/30min-compare/$ITER/70-*compare*.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/$ITER/

done


cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-RandomForwardLoadBalancer/50-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-RandomForwardLoadBalancer-loadAvg.png
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-RandomForwardLoadBalancer/70-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-RandomForwardLoadBalancer-loadAvg.png

cp /extra/alfuerst/openwhisk-logs/30min-compare/1/50-ShardingContainerPoolBalancer/50-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/50-ShardingContainerPoolBalancer-loadAvg.png
cp /extra/alfuerst/openwhisk-logs/30min-compare/1/70-ShardingContainerPoolBalancer/70-loadAvg.png /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/70-ShardingContainerPoolBalancer-loadAvg.png

for USERS in 30 50 70
do

python3 compare_latencies.py --path /extra/alfuerst/vary-ceil-30min/*/*/* --users $USERS
python3 plot_tputs.py --path /extra/alfuerst/vary-ceil-30min/*/*/* --users $USERS --ceil

mv *invokes-ceil.png "/home/alfuerst/repos/faaslb-osdi22/figs/overload-compare/"
mv *compare-overload*png "/home/alfuerst/repos/faaslb-osdi22/figs/overload-compare/"

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/* --users $USERS

mv *invokes.png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/"
mv *compare-functions*.png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare/"

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/bursty/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/bursty/*/* --users $USERS

mv *invokes.png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"
mv *compare-functions*.png "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"

done

