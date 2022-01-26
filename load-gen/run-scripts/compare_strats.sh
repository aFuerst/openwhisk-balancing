#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=5e9fb463-3082-4fce-847b-dbc17a7fbfa0:AZcoEhmD4dMsFTu7SPOAI4NkyDqtyaqkbxyud5bnMW5MssmPtQoC9BggNweGcJIj

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
