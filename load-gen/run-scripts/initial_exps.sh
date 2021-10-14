#!/bin/bash

# 15 GB - 96 cold
# 10 GB - 112 cold
# 8 GB - 141 cold
# 6 GB - 374 cold

# interesting combos:
# 4 CPUs:
#   8 GB - 141 cold
#   6 GB - 374 cold
#
#

IMAGE="alfuerst"
CPUS=4
GBS=8
GBstr="$GBS"
GBstr+="G"
STRAT="SimpleLoad"
MINS=10

#  "ConsistentHash"
for ALGO in "ConsistentCache" "BoundedLoad"
do
dir="logs/$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/$CPUS-$GBS-$ALGO-$STRAT.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done

MINS=20
for ALGO in "ConsistentCache" "BoundedLoad" "ConsistentHash"
do
dir="logs/$MINS-mins-$CPUS-$GBS-$ALGO-$STRAT"
PTH="$dir/$CPUS-$GBS-$ALGO-$STRAT.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
done

IMAGE="whisk"
ALGO="MemoryShard"
dir="logs/$MINS-mins-$CPUS-$GBS-$ALGO"
PTH="$dir/$CPUS-$GBS-$ALGO.csv"
echo $PTH
mkdir -p $dir
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS &> "$dir/$CPUS-$GBS-$ALGO.log"
./gatherlogs.sh $dir
