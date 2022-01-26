import os, sys
from collections import defaultdict
import argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 12})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--ttl", nargs='+', required=False)
parser.add_argument("--users", type=int, default=100, required=False)
parser.add_argument("--balancers", nargs='+', required=True)
parser.add_argument("--loc", type=str, required=False)
args = parser.parse_args()

def path_to_lb(pth):
  # print(pth)
  parts = pth.split("/")
  # print(parts)

  return parts[-1].split("-")[1]

def plot(paths, ttls, users):
  warm_dict = defaultdict(list)
  cold_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if not "/" + str(users) + "-" in pth:
      continue
    if path_to_lb(pth) not in args.balancers:
      continue
    df = pd.read_csv(file)

    warm = len(df[df["cold"] == False])
    cold = len(df[df["cold"] == True])

    warm_dict[path_to_lb(pth)].append(warm)
    cold_dict[path_to_lb(pth)].append(cold)

  for ttl_pth in ttls:
    file = os.path.join(ttl_pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if not "/" + str(users) + "-" in ttl_pth:
      continue
    df = pd.read_csv(file)
    warm = len(df[df["cold"] == False])
    cold = len(df[df["cold"] == True])

    # print(file, len(df))
    # print(ttl_pth, warm + cold)

    warm_dict["TTL"].append(warm)
    cold_dict["TTL"].append(cold)
  # print(warm_dict)
  # print(cold_dict)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer':'CH-BL', 'RandomForwardLoadBalancer':'Random', 'RoundRobinLB':'RR', 'ShardingContainerPoolBalancer':'OW+GD', 'TTL':'OW+TTL',
              'GreedyBalancer': 'Greedy', 'RandomLoadUpdateBalancer': 'old_RLU',
              "EnhancedShardingContainerPoolBalancer": "Enhance", "RLUShardingBalancer": "RLU_shard", "LeastLoadBalancer": "LL",
              "RLULFSharding": "RLU"}
  labels = [map_labs[x] for x in sorted(warm_dict.keys())]
  # print(labels)
  colds = []
  colds_std = []
  warms = []
  warms_std = []
  for lb in sorted(warm_dict.keys()):
    warms.append(sum(warm_dict[lb]) / len(warm_dict[lb]))
    warms_std.append(np.std(warm_dict[lb]))
    colds.append(sum(cold_dict[lb]) / len(cold_dict[lb]))
    colds_std.append(np.std(cold_dict[lb]))

  ax.bar(labels, colds, label="Cold", yerr=colds_std)
  ax.bar(labels, warms, bottom=colds, label="Warm", yerr=warms_std)
  
  save_fname = os.path.join("{}-invokes-ttl.pdf".format(args.users))

  ax.set_ylabel("Invocations")
  ax.set_xlabel("LoadBalancing Policy")
  ax.legend(loc='center right' if args.loc is None else args.loc)
  # print(save_fname)

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


plot(args.path, args.ttl, args.users)
