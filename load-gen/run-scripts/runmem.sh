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

for CPUS in 5 6
do

for GBS in 6 8 10 12
do
  GBstr="$GBS"
  GBstr+="G"
  PTH="logs/$CPUS-$GBS.csv"
  ./oneexp.sh --memory $GBstr --loadstrat "LoadAvg" --algorithm "ConsistentCache" --image $IMAGE --output $PTH --cpus $CPUS &> "logs/$CPUS-$GBS.log"
done

done


