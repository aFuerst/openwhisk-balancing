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

ALGO="ConsistentCache"
PTH="logs/$CPUS-$GBS-$ALGO.csv"
echo $PTH
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS &> "logs/$CPUS-$GBS-$ALGO.log"


ALGO="BoundedLoad"
PTH="logs/$CPUS-$GBS-$ALGO.csv"
echo $PTH
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS &> "logs/$CPUS-$GBS-$ALGO.log"


IMAGE="whisk"
ALGO="MemoryShard"
PTH="logs/$CPUS-$GBS-$ALGO.csv"
echo $PTH
./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS &> "logs/$CPUS-$GBS-$ALGO.log"

