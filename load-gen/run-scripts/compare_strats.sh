#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=3012593d-2f77-4991-8413-17fb04f74f9d:haEBFhaLcFregYZMfNcein4YxBGvg85VCF4pSgKqCGoCpHzCna0s6ZbPoXhLa0t4

for STRAT in "SimpleLoad" "Running" "RAndQ" "LoadAvg"
do
dir="logs/compare-strats/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory "18G" --loadstrat $STRAT --algorithm "ConsistentCache" --output $PTH --cpus 5.5 --lenmins 10 --evict "GD" --balancer "ConsistentCacheLoadBalancer" &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done
