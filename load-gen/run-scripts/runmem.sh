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
ALGO="ConsistentCache"
STRAT="SimpleLoad"
MINS=10

export HOST=https://172.29.200.161:10001
export AUTH=5e9fb463-3082-4fce-847b-dbc17a7fbfa0:AZcoEhmD4dMsFTu7SPOAI4NkyDqtyaqkbxyud5bnMW5MssmPtQoC9BggNweGcJIj

for GBS in 16 18
do
  # for USERS in 80 100 150 200
  # do
  for CPUS in 5.5 6 6.5 7 8
  do

  GBstr="$GBS"
  GBstr+="G"
  dir="logs/explore/$CPUS-$GBS"
  PTH="$dir/$CPUS-$GBS.csv"
  echo $PTH
  mkdir -p $dir
  # ./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --users $USERS --lenmins $MINS &> "$dir/$USERS-$GBS.log"
  ./oneexp.sh --memory $GBstr --loadstrat $STRAT --algorithm $ALGO --image $IMAGE --output $PTH --cpus $CPUS --lenmins $MINS &> "$dir/$CPUS-$GBS.log"
  ./gatherlogs.sh $dir
 done
done


