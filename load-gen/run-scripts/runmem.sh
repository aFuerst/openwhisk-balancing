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

export HOST=https://172.29.200.161
export AUTH=3012593d-2f77-4991-8413-17fb04f74f9d:haEBFhaLcFregYZMfNcein4YxBGvg85VCF4pSgKqCGoCpHzCna0s6ZbPoXhLa0t4

for GBS in 10 12
do
  # for USERS in 80 100 150 200
  # do
  for CPUS in 4 5 6 7
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


