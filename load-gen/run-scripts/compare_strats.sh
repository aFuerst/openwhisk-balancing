#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=a0ebde37-0272-4d2e-b2ed-77f93f9e0158:WW5BI37G7ppqVPnOAgapbsUxGirIsBo1iXATp7ufGdK5wO44CbPbQvtUbCdHxU50

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
