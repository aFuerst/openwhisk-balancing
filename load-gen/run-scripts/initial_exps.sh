#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=2808ef88-a07b-4c0a-b43c-35aae16b23f1:uSBzPCl92yjKFWTEOFulTWFUlXttpAIOOp50b1fsIu0xULSoHlEQzqhpgGXbetEk

CPUS=5.5
GBS=18
GBstr="$GBS"
GBstr+="G"
STRAT="SimpleLoad"
MINS=10
BALANCER="ConsistentCacheLoadBalancer"
EVICTION="GD"

for ALGO in "ConsistentCache" "BoundedLoad" "RoundRobin"
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
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir

ALGO="RandomPass"
BALANCER="ConsistentRandomLoadBalancer"
dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir

# CPUS=5
# STRAT="SimpleLoad"
# BALANCER="ConsistentCacheLoadBalancer"
# MINS=20
# for ALGO in "ConsistentCache" "BoundedLoad" "ConsistentHash" "RoundRobin"
# do
# dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
# PTH="$dir/latencies.csv"
# echo $PTH
# mkdir -p $dir
# ./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
# ./gatherlogs.sh $dir
# done

# IMAGE="whisk"
# ALGO="MemoryShard"
# BALANCER="ShardingContainerPoolBalancer"
# dir="logs/compare-algos/$MINS-mins-$CPUS-$GBS-$ALGO"
# PTH="$dir/latencies.csv"
# echo $PTH
# mkdir -p $dir
# ./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
# ./gatherlogs.sh $dir