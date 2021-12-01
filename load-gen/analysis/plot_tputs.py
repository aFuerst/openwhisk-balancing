import os, sys
from collections import defaultdict
import argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

def path_to_lb(pth):
  parts = pth.split("/")
  return parts[-1].split("-")[1]

def plot(paths, users):
  mean_sums = defaultdict(int)
  warm_dict = defaultdict(list)
  cold_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file) or not str(users) in pth:
      continue
    df = pd.read_csv(file)

    warm = len(df[df["cold"] == False])
    cold = len(df[df["cold"] == True])

    warm_dict[path_to_lb(pth)].append(warm)
    cold_dict[path_to_lb(pth)].append(cold)
  # print(warm_dict)
  # print(cold_dict)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer':'Bounded', 'RandomForwardLoadBalancer':'Random', 'RoundRobinLB':'RR', 'ShardingContainerPoolBalancer':'Sharding'}
  labels = [map_labs[x] for x in sorted(warm_dict.keys())]
  print(labels)
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
  
  save_fname = os.path.join("{}-invokes.png".format(args.users))

  ax.set_ylabel("Invocations")
  ax.set_ylabel("LoadBalancing Policy")
  ax.legend()
  print(save_fname)

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


plot(args.path, args.users)
