#!/bin/bash

export HOST=https://172.29.200.161:10001
export AUTH=5973c02d-4c68-4b6d-af13-17f9e3e82028:ezIS6fF9BREmaMLGZrVDT7Y3SauPQdt7u1rNsDnHhUPweeC186J0OePoe1kabdh4

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

