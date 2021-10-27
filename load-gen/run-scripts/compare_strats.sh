#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=a6146758-674e-4bdf-990a-c6affc45b696:e7M1kFyxOxNNbVnMVUhghe1A3Rs7tF0T2NX2bPkWrMRMdZaWp5XEotqtT6FwM8Co

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
