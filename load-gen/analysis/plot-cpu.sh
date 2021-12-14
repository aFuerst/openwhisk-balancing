#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 20 50 # 70
do

for BAL in ShardingContainerPoolBalancer RandomLoadUpdateBalancer
do

if [ -d "/extra/alfuerst/openwhisk-logs/30min-compare-cpu/$ITER/$USERS-$BAL/" ]; then
python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs/30min-compare-cpu/$ITER/$USERS-$BAL/" $USERS
fi

done

done

done

cp /extra/alfuerst/openwhisk-logs/30min-compare-cpu/0/20-ShardingContainerPoolBalancer/20-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/20-ShardingContainerPoolBalancer-loadAvg.pdf
cp /extra/alfuerst/openwhisk-logs/30min-compare-cpu/0/20-RandomLoadUpdateBalancer/20-loadAvg.pdf /home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/20-RandomLoadUpdateBalancer-loadAvg.pdf

for USERS in 20 50
do

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare-cpu/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/30min-compare-cpu/*/* --users $USERS

mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/"
mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/"


done
