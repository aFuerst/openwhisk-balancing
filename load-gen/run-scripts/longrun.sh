#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=a0ebde37-0272-4d2e-b2ed-77f93f9e0158:WW5BI37G7ppqVPnOAgapbsUxGirIsBo1iXATp7ufGdK5wO44CbPbQvtUbCdHxU50

CPUS=5
GBS=18
GBstr="$GBS"
GBstr+="G"
STRAT="SimpleLoad"
MINS=30
BALANCER="ConsistentCacheLoadBalancer"
EVICTION="GD"

for ALGO in "ConsistentCache" "BoundedLoad" "RoundRobin"
do
dir="logs/long-run/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT-$EVICTION"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done

ALGO="MemoryShard"
BALANCER="ShardingContainerPoolBalancer"
dir="logs/long-run/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT-$EVICTION"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir

EVICTION="TTL"
dir="logs/long-run/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT-$EVICTION"
PTH="$dir/latencies.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS --evict $EVICTION --balancer $BALANCER &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir

