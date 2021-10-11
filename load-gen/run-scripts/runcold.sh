#!/bin/bash

IMAGE="alfuerst"

for CPUS in 4 5 6 7
do

for GBS in 6 8 10 12 14
do
  GBstr = "$GBS" + "G"
  ./oneexp.sh --memory $GBstr --loadstrat "ConsistentCache" --algorithm "LoadAvg" --image $IMAGE --output "" --cpus $CPUS
done

done


