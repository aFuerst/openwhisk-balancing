#!/bin/bash

python3 paper/plot_openload_data.py --path /extra/alfuerst/openwhisk-logs-two/openload/*/*/

for ITER in {0..3}
do

python3 plot_invoker_load.py /extra/alfuerst/openwhisk-logs-two/openload/$ITER/ShardingContainerPoolBalancer/ 10
python3 plot_invoker_load.py /extra/alfuerst/openwhisk-logs-two/openload/$ITER/RLULFSharding/ 10

done

cp /extra/alfuerst/openwhisk-logs-two/openload/0/ShardingContainerPoolBalancer/trace.pdf openload/trace.pdf
cp /extra/alfuerst/openwhisk-logs-two/openload/0/ShardingContainerPoolBalancer/10-loadAvg.pdf openload/ShardingContainerPoolBalancer-loadAvg.pdf  
cp /extra/alfuerst/openwhisk-logs-two/openload/0/RLULFSharding/10-loadAvg.pdf openload/RLULFSharding-loadAvg.pdf  

cp ./openload/* /home/alfuerst/repos/faaslb-osdi22/figs/ow/openload/