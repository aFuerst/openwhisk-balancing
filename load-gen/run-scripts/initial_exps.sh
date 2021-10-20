#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=3012593d-2f77-4991-8413-17fb04f74f9d:haEBFhaLcFregYZMfNcein4YxBGvg85VCF4pSgKqCGoCpHzCna0s6ZbPoXhLa0t4

CPUS=5.5
GBS=18
GBstr="$GBS"
GBstr+="G"
STRAT="SimpleLoad"
MINS=10
BALANCER="ConsistentCacheLoadBalancer"
EVICTION="GD"

for ALGO in "ConsistentCache" "BoundedLoad" "ConsistentHash" "RoundRobin"
do
dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done

ALGO="MemoryShard"
BALANCER="ShardingContainerPoolBalancer"
dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir

CPUS=5
STRAT="SimpleLoad"
BALANCER="ConsistentCacheLoadBalancer"
MINS=20
for ALGO in "ConsistentCache" "BoundedLoad" "ConsistentHash" "RoundRobin"
do
dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done

IMAGE="whisk"
ALGO="MemoryShard"
BALANCER="ShardingContainerPoolBalancer"
dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
