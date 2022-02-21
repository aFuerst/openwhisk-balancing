#!/bin/bash

for USERS in 20 50
do

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Random* /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Round* /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Bounded* /extra/alfuerst/openwhisk-logs/30min-compare-TTL/*/* --users $USERS
python3 compare_function.py --path /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Random* /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Round* /extra/alfuerst/openwhisk-logs/30min-compare/*/*-Bounded* /extra/alfuerst/openwhisk-logs/30min-compare-TTL/*/* --users $USERS

mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-ttl/"
mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-compare-ttl/"

python3 plot_tputs.py --path /extra/alfuerst/openwhisk-logs/bursty-2/*/*-Random* /extra/alfuerst/openwhisk-logs/bursty-2/*/*-Round* /extra/alfuerst/openwhisk-logs/bursty-2/*/*-Bounded* /extra/alfuerst/openwhisk-logs/30min-compare-TTL-bursty/*/* --users $USERS

mv *invokes.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"
mv *compare-functions*.pdf "/home/alfuerst/repos/faaslb-osdi22/figs/30min-bursty/"

done
