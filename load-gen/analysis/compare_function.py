from collections import defaultdict
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import argparse


parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=50, required=False)
args = parser.parse_args()

path = args.path[1]
users = args.users
# for p in args.path:
#   print(p)

rand_str = "RandomForwardLoadBalancer"
bound_str = "BoundedLoadsLoadBalancer"
rr_str = "RoundRobinLB"
shard_str = "ShardingContainerPoolBalancer"
rlu_str = "RandomLoadUpdateBalancer"

base_file = "parsed_successes.csv"

out=[]
warm_times = [0.3525, 3.035, 1.344, 0.2484, 0.8558, 0.3944, 6.7276, 0.2661, 9.1485, 0.7716, 6.1336, 0.4874]
min_warm_times = [0.05505, 1.6623, 0.24349, 0.044388, 0.33531, 0.03527, 6.44305, 0.03420, 8.06751, 0.60664, 6.06870, 0.10007]
actions = ["cham", "cnn", "dd", "float", "gzip", "hello", "image", "lin_pack", "train", "aes", "video", "json"]
tmp = pd.read_csv(os.path.join(path, base_file))
func_names = tmp["function"].unique()
for warm_time, k in zip(min_warm_times, actions):
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
      # print(counts['cham_16'])
    else:
      mean_warm = mean_warm.add(pd.Series(mean_lats['latency'], index=mean_warm.index))
      counts = counts.add(lgrps['latency'].count())
      # print(lgrps['latency'].count()['cham_16'])
    # print(counts.index[0])
    # print("tot:", counts['cham_16'])
    # print(counts[counts.index[0]])
    # print(counts)
  mean_warm /= len(expfs)
  norm_warm = pd.Series(mean_warm/warm_times['warm'], index=mean_warm.index)

  # counts = lgrps.count()
  # counts = counts.rename(columns={'latency':'counts'})
  # mean_warm = mean_warm.merge(counts, on='function')
  C=sum(counts)
  mean_warm = pd.Series((norm_warm*counts)/C, index=mean_warm.index)
  # print(mean_warm)
  return mean_warm, counts
  #sum(mean_warm['Wnorm'])

def compare(numerator_str, denom_str, paths):
  numerator_paths = []
  # print("{}-{}".format(users, numerator_str))
  for pth in paths:
    if "{}-{}".format(users, numerator_str) in pth and os.path.exists(os.path.join(pth, base_file)):
      # print("num", pth)
      numerator_paths.append(os.path.join(pth, base_file))
  if len(numerator_paths) == 0:
    return
  # numerator_path = os.path.join(path, "{}-{}".format(users, numerator_str), base_file)
  # print(numerator_str)
  numerator, num_counts = Wnorms(numerator_paths)
  # sum(bounded['Wnorm'])
  # print(numerator)
  # denom_path = os.path.join(path, "{}-{}".format(users, denom_str), base_file)
  denom_paths = []
  # print("{}-{}".format(users, denom_str))
  for pth in paths:
    if "{}-{}".format(users, denom_str) in pth and os.path.exists(os.path.join(pth, base_file)):
      # print("demon", pth)
      denom_paths.append(os.path.join(pth, base_file))
  if len(denom_paths) == 0:
    return
  # print(denom_str)
  denom, demon_counts =Wnorms(denom_paths)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)

  compared = numerator/denom
  # print(sorted(compared))
  ax.hlines(1.0, xmin=-0.1, xmax=len(compared)+1-.9, color='black')

  # ax.plot(sorted(compared),marker='o',alpha=0.3)

  ymin = []
  ymax = []
  for pt in sorted(compared):
    if pt <= 1:
      ymin.append(pt)
      ymax.append(1)
    else:
      ymin.append(1)
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
  ax.vlines([len(compared)], 1, avg, color='red')
  handles.append(mpatches.Patch(color="red", label='Global Average'))
  ax.legend(handles=handles, loc='upper left')#, labels=leg_labels)

  # ax.set_ylabel("Invoker {}".format(metric))
  ax.set_ylabel("Normalized latency")
  # ax.legend()
  # ax.set_yscale('log')

  map_labs = {'BoundedLoadsLoadBalancer': 'Bounded', 'RandomForwardLoadBalancer': 'Random Forward',
            'RoundRobinLB': 'Round Robin', 'ShardingContainerPoolBalancer': 'Sharding', 'RandomLoadUpdateBalancer': 'RLU',
            "EnhancedShardingContainerPoolBalancer":"Enhance"}

  ax.set_title("{} / {}".format(map_labs[numerator_str], map_labs[denom_str]))
  save_fname = os.path.join("{}-compare-functions-{}-{}.pdf".format(users, numerator_str, denom_str))
  print(save_fname, avg)
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

compare(shard_str, bound_str, args.path)
compare(shard_str, rand_str, args.path)
compare(bound_str, rand_str, args.path)
compare(rr_str, rand_str, args.path)
compare(shard_str, rlu_str, args.path)
compare(bound_str, rlu_str, args.path)

compare(rand_str, rlu_str, args.path)
