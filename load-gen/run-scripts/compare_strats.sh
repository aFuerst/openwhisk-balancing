#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=5973c02d-4c68-4b6d-af13-17f9e3e82028:ezIS6fF9BREmaMLGZrVDT7Y3SauPQdt7u1rNsDnHhUPweeC186J0OePoe1kabdh4

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
