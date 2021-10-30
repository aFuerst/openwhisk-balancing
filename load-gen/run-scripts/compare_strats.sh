#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=2808ef88-a07b-4c0a-b43c-35aae16b23f1:uSBzPCl92yjKFWTEOFulTWFUlXttpAIOOp50b1fsIu0xULSoHlEQzqhpgGXbetEk

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
