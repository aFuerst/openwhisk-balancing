#!/bin/bash

for ITER in 0 1 2 3
do

for USERS in 120
do

for BAL in EnhancedShardingContainerPoolBalancer RLUShardingBalancer
do

for CEIL in {1..11}
do

python3 plot_invoker_load.py "/extra/alfuerst/openwhisk-logs-two/vary-ceil/$ITER/compare-$CEIL/$USERS-$BAL" $USERS &
python3 map_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/vary-ceil/$ITER/compare-$CEIL/$USERS-$BAL" $USERS &
python3 scatter_invocation_to_load.py "/extra/alfuerst/openwhisk-logs-two/vary-ceil/$ITER/compare-$CEIL/$USERS-$BAL" $USERS &
python3 latency_over_time.py --path "/extra/alfuerst/openwhisk-logs-two/vary-ceil/$ITER/compare-$CEIL/$USERS-$BAL" --users $USERS &

done
done
done
done

for BAL in EnhancedShardingContainerPoolBalancer RLUShardingBalancer
do

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs-two/vary-ceil/*/compare-*/120-$BAL --users 120 --ceil
mv 120-throughputs-ceil.pdf $BAL-120-throughputs-ceil.pdf
python3 plot_invocations.py --path /extra/alfuerst/openwhisk-logs-two/vary-ceil/*/compare-*/120-$BAL --users 120 --ceil
python3 compare_latencies.py --path /extra/alfuerst/openwhisk-logs-two/vary-ceil/*/compare-*/120-$BAL --users 120
mv 120-compare-overload.pdf $BAL-120-compare-overload.pdf
mv 120-compare-overload-warm.pdf $BAL-120-compare-overload-warm.pdf

# mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/"
# mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-cpu/"


done
