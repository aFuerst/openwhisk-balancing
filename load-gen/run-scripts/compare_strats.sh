#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=e0ddac86-ac5a-45e0-bf37-ec3dcf3f70de:WwX7nwMvLWHQhW2vjZtyZkL8QVTcKa4PplCp2riFYn49TnBogJb21V09EcEzIw2D

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/10-mins-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$STRAT.log"
./gatherlogs.sh $dir
done
