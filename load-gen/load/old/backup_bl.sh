#!/bin/bash

for ITERATION in {0..3}
do

for USERS in 50 30 70
do

# RandomForwardLoadBalancer ShardingContainerPoolBalancer RoundRobinLB BoundedLoadsLoadBalancer RandomLoadUpdateBalancer
for BALANCER in RandomLoadUpdateBalancer
do

BASEPATH="/extra/alfuerst/openwhisk-logs/30min-compare/$ITERATION/$USERS-$BALANCER"

if [ -f "$BASEPATH/controller0_logs.log" ]; then
new="/extra/alfuerst/openwhisk-logs/30min-compare-bak/$ITERATION/$USERS-$BALANCER"
echo "moving $BASEPATH to $new"
mkdir -p $new
mv -f $BASEPATH $new
fi

done
done
done