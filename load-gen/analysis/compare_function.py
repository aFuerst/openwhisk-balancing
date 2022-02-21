from collections import defaultdict
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 12})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import argparse
import pickle

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--ttl", action="store_true")
parser.add_argument("--plotglobal", action="store_true")
parser.add_argument("--users", type=int, default=50, required=False)
args = parser.parse_args()

users = args.users
# for p in args.path:
#   print(p)

base_file = "parsed_successes.csv"

warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

min_warm_times = {}
for k in warm_results.keys():
  min_warm_times[k] = min(warm_results[k])

for i in range(len(args.path)):
  path = os.path.join(args.path[0], "parsed_successes.csv")
  if os.path.exists(path):
    tmp = pd.read_csv(path)
    break
if tmp is None:
  exit(0)
func_names = tmp["function"].unique()
out = []
for k, warm_time in min_warm_times.items():
  for name in func_names:
    if k in name:
      out.append((name,warm_time))
warm_times = pd.DataFrame(out,columns=['function',"warm"])
warm_times.index = warm_times['function']

def get_warm_times(df):
  warmed = df[df["cold"] == False]
  colded = df[df["cold"] == True]
  warm_means = warmed.groupby(['function'])["latency"].mean()
  # print(warm_means.isna())
  cold_means = colded.groupby(['function'])["latency"].mean()
  return warm_means, cold_means

def mean_lats_per_fn(expf):
  df = pd.read_csv(expf, header=0, usecols=["function", "cold", "latency", "activation_id"])
  # df = df[df['cold']==False]
  ldf = df[['function', 'latency']]
  lgrps = ldf.groupby(['function'])
  #Also need the length of the list for correct normalization? 
  mean_lats = lgrps.mean()
  return mean_lats, lgrps, ldf, df 

def cmp_lats(f1, f2):
    """ Given two configs, compare the raw mean latencies for each function """
    m1 = mean_lats_per_fn(f1)[0]
    m2 = mean_lats_per_fn(f2)[0]
    merged = m1.merge(m2,on='function')
    merged['ldiff'] = pd.Series(merged['latency_y']-merged['latency_x'], index=merged.index)
    return merged

def Wnorms(expfs):
  mean_warm = None
  counts = None
  for expf in expfs:
    mean_lats, lgrps, ldf, df = mean_lats_per_fn(expf)
    if mean_warm is None:
      mean_warm = pd.Series(mean_lats['latency'], index=mean_lats.index)
      counts = lgrps['latency'].count()
      # if any(counts.isna()):
      #   print("nan count orig")
      #   print(lgrps[lgrps['latency'].count().isna()])
      # print(counts['cham_16'])
    else:
      mean_warm = mean_warm.add(
          pd.Series(mean_lats['latency'], index=mean_warm.index), fill_value=0)
      counts = counts.add(lgrps['latency'].count(), fill_value=0)
      # if any(counts.isna()):
      #   print("nan count")
      #   print(counts)
      #   for name, grp in lgrps:
      #     if len(grp) <= 1:
      #       print(name, len(grp))
      #     if name == "gzip_1.1":
      #       print(name, grp)
      #   print("is nan: ",counts[counts.isna()])
      #   exit()
      # print(lgrps['latency'].count()['cham_16'])
    # print(counts.index[0])
    # print("tot:", counts['cham_16'])
    # print(counts[counts.index[0]])
    # print(counts)
  # if "LeastLoadBalancer" in expfs[0]:
  #   print(mean_warm)
  mean_warm /= len(expfs)
  norm_warm = pd.Series(mean_warm/warm_times['warm'], index=mean_warm.index)
  # if "LeastLoadBalancer" in expfs[0]:
  #   print(mean_warm)
  #   print(norm_warm)

  # counts = lgrps.count()
  # counts = counts.rename(columns={'latency':'counts'})
  # mean_warm = mean_warm.merge(counts, on='function')
  C=sum(counts)
  mean_warm = pd.Series((norm_warm*counts)/C, index=mean_warm.index)
  # if "LeastLoadBalancer" in expfs[0]:
  #   print(lgrps["function"].groups["gzip_1.1"])
  #   print("counts", counts[counts.isna()])
  #   print(mean_warm)
  return mean_warm, counts
  #sum(mean_warm['Wnorm'])

def compare(numerator_str, denom_str, paths):
  if numerator_str == denom_str:
    raise Exception("Cannot compare function to itself!!")
  numerator_paths = []
  # print("{}-{}".format(users, numerator_str))
  for pth in paths:
    if "/{}-{}".format(users, numerator_str) in pth and os.path.exists(os.path.join(pth, base_file)):
      # print("num", pth)
      numerator_paths.append(os.path.join(pth, base_file))
  if len(numerator_paths) == 0:
    print("num err", numerator_str)
    return
  # numerator_path = os.path.join(path, "{}-{}".format(users, numerator_str), base_file)
  # print(numerator_str)
  # print(numerator_paths)
  numerator, num_counts = Wnorms(numerator_paths)
  # print(numerator_str, numerator[numerator.isna()])
  # sum(bounded['Wnorm'])
  # print(numerator)
  # denom_path = os.path.join(path, "{}-{}".format(users, denom_str), base_file)
  denom_paths = []
  # print("{}-{}".format(users, denom_str))
  for pth in paths:
    if "/{}-{}".format(users, denom_str) in pth and os.path.exists(os.path.join(pth, base_file)):
      # print("demon", pth)
      denom_paths.append(os.path.join(pth, base_file))
  if len(denom_paths) == 0:
    print("demon err", denom_str)
    return
  # print(denom_str)
  denom, demon_counts = Wnorms(denom_paths)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)

  compared = numerator/denom
  # print(sorted(compared))

  base = 0.0

  ax.hlines(base, xmin=-0.1, xmax=len(compared)-.9, color='black')
  if args.plotglobal:
    ax.hlines(base, xmin=-0.1, xmax=len(compared)+1-.9, color='black')

  # ax.plot(sorted(compared),marker='o',alpha=0.3)

  ymin = []
  ymax = []
  for pt in sorted(compared):
    if pt <= 1.0:
      ymin.append(-1.0/pt)
      ymax.append(base)
    else:
      ymin.append(base)
      ymax.append(pt)
  
  handles= []
  ax.vlines([i for i in range(len(ymin))],ymin,ymax, color='blue')
  handles.append(mpatches.Patch(color="blue", label='Function'))

  weighted_total = 0
  total = 0
  for idx in compared.index:
    weighted_total += compared[idx] * (num_counts[idx] + demon_counts[idx])
    total += num_counts[idx] + demon_counts[idx]

  avg = weighted_total / total
  if args.plotglobal:
    ax.vlines([len(compared)], base, avg, color='red')
    handles.append(mpatches.Patch(color="red", label='Global Average'))
    ax.legend(handles=handles, loc='upper left')#, labels=leg_labels)

  # ax.set_ylabel("Invoker {}".format(metric))
  ax.set_ylabel("Relative function latency")
  # ax.legend()
  # ax.set_yscale('log')

  map_labs = {'BoundedLoadsLoadBalancer': 'CH-BL', 'RandomForwardLoadBalancer': 'Random Forward',
            'RoundRobinLB': 'Round Robin', 'ShardingContainerPoolBalancer': 'OW+GD', 'TTL': 'OW+TTL',
            "EnhancedShardingContainerPoolBalancer":"Enhance", "RLUShardingBalancer":"RLU", "LeastLoadBalancer":"LL",
            "RLULFSharding":"RLU"}

  if args.ttl:
    if numerator_str == "ShardingContainerPoolBalancer":
      numerator_str = "TTL"
    if denom_str == "ShardingContainerPoolBalancer":
      denom_str = "TTL"
  plt.setp(ax.get_xticklabels(), visible=False)
  ax.tick_params(axis='both', which='both', length=0)
  ax.set_title("{} / {}".format(map_labs[numerator_str], map_labs[denom_str]))
  save_fname = os.path.join("{}-compare-functions-{}-{}.pdf".format(users, numerator_str, denom_str))
  if args.plotglobal:
    save_fname = os.path.join("{}-compare-functions-{}-{}-global.pdf".format(users, numerator_str, denom_str))
  print(save_fname, avg)
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

rand_str = "RandomForwardLoadBalancer"
bound_str = "BoundedLoadsLoadBalancer"
rr_str = "RoundRobinLB"
shard_str = "ShardingContainerPoolBalancer"
rlu_str = "RLULFSharding"
enhance="EnhancedShardingContainerPoolBalancer"

compare(shard_str, rlu_str, args.path)
compare("LeastLoadBalancer", rlu_str, args.path)
 