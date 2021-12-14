#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=16e211d7-9559-4c7e-9f33-cf32d5f1b8e0:jFZq1YnhzHIiMHwHK7kuZ7ZBaISXY75dV6WhNDZPV6iivSwzhocyVFYuqMzOmjLx

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
