from collections import defaultdict
import os
import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

path = args.path
users = args.users

def path_to_lb(pth):
  parts = pth.split("/")
  return parts[-1].split("-")[1]

def get_push_dist(line):
  if "full circle" in line:
    return 8

  marker = "was pushed "
  pos = line.find(marker)
  dist_start = pos + len(marker)  # line[pos:len(marker)]
  dist_end = line.find(" ", dist_start)
  return int(line[dist_start:dist_end])
  # print(dist_start, dist_end, dist)

pct_pushed = defaultdict(list)
pct_pop = defaultdict(list)
pct_unpop = defaultdict(list)
tot_pushed = defaultdict(list)
pop_push_dist = defaultdict(list)
unpop_push_dist = defaultdict(list)

for pth in path:
  file = os.path.join(pth, "controller0_logs.log")
  if not os.path.exists(file):
    continue
  if not str(users) + "-" in pth:
    continue
  transactions = os.path.join(pth, "logs_transactions.csv")
  df = pd.read_csv(transactions)

  pop_distances = []
  unpop_distances = []
  key = path_to_lb(pth)
  with open(file) as f:
    for line in f:
      if "pushed invocation " in line:
        marker = "invocation "
        pos = line.find(marker)
        dist_start = pos + len(marker)  # line[pos:len(marker)]
        dist_end = line.find(" ", dist_start)
        dist = int(line[dist_start:dist_end])
        pop_distances.append(dist)

      if "pushed popular invocation " in line:
        marker = "invocation "
        pos = line.find(marker)
        dist_start = pos + len(marker)  # line[pos:len(marker)]
        dist_end = line.find(" ", dist_start)
        dist = int(line[dist_start:dist_end])
        pop_distances.append(dist)
      elif "unpopular Activation was pushed " in line:
        marker = "was pushed "
        pos = line.find(marker)
        dist_start = pos + len(marker)  # line[pos:len(marker)]
        dist_end = line.find(" ", dist_start)
        dist = int(line[dist_start:dist_end])
        unpop_distances.append(dist)

      elif "system is overloaded" in line:
        if "unpopular" in line:
          unpop_distances.append(3)
        else:
          pop_distances.append(3)
      elif "was pushed" in line:
        dist = get_push_dist(line)
        if "unpopular" in line:
          # [2021-12-12T06:58:51.229Z] [INFO] [#tid_gFHGdfpJp9s17uO9HUJeLLEaN2SOEEn4] [RandomLoadUpdateBalancer] unpopular Activation ab6c05de03b24b07ac05de03b2eb072b was pushed 1 places to invoker3/3, from invoker5/5
          unpop_distances.append(dist)
        else:
          # popular function
          # [2021-12-12T06:58:57.730Z] [INFO] [#tid_RexpWoWoXnDN2ZV66VKAVUF2upi8sgwp] [RandomLoadUpdateBalancer] unpopular Activation 34c158acaf05412e8158acaf05412ec4 was pushed 1 places to invoker3/3, from invoker5/5
          pop_distances.append(dist)
  pushed = len(unpop_distances) + len(pop_distances)
  pct_pushed[key].append(pushed / len(df))
  if pushed == 0:
    pct_pop[key].append(0)
    pct_unpop[key].append(0)
  else:
    pct_pop[key].append( len(pop_distances) / pushed)
    pct_unpop[key].append( len(unpop_distances) / pushed)
  tot_pushed[key].append(len(unpop_distances) + len(pop_distances))
  pop_push_dist[key] += pop_distances
  unpop_push_dist[key] += unpop_distances

print("Balancer, avg_pct_pushed, avg_pop_push, avg_unpop_push, pct_pop, pct_unpop")
for key in pct_pushed.keys():
  if len(pct_pushed[key]) == 0:
    avg_pct_pushed = 0
  else:
    avg_pct_pushed = sum(pct_pushed[key]) / len(pct_pushed[key])
  avg_pct_pushed *= 100

  if len(pop_push_dist[key]) == 0:
    avg_pop_push = 0
  else:
    avg_pop_push = sum(pop_push_dist[key]) / len(pop_push_dist[key])
  
  if len(unpop_push_dist[key]) == 0:
    avg_unpop_push = 0
  else:
    avg_unpop_push = sum(unpop_push_dist[key]) / len(unpop_push_dist[key])

  if len(pct_unpop[key]) == 0:
    avg_pct_unpop = 0
  else:
    avg_pct_unpop = sum(pct_unpop[key]) / len(pct_unpop[key])
  avg_pct_unpop *= 100

  if len(pct_pop[key]) == 0:
    avg_pct_pop = 0
  else:
    avg_pct_pop = sum(pct_pop[key]) / len(pct_pop[key])
  avg_pct_pop *= 100

  print("{}, {}, {}, {}, {}, {}".format(key, avg_pct_pushed, avg_pop_push, avg_unpop_push, avg_pct_pop, avg_pct_unpop))
