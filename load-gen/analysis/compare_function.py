from collections import defaultdict
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
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

path = args.path[0]
users = args.users

rand_str = "RandomForwardLoadBalancer"
bound_str = "BoundedLoadsLoadBalancer"
rr_str = "RoundRobinLB"
shard_str = "ShardingContainerPoolBalancer"

base_file = "parsed_successes.csv"

out=[]
warm_times = [0.3525, 3.035, 1.344, 0.2484, 0.8558, 0.3944, 6.7276, 0.2661, 9.1485, 0.7716, 6.1336, 0.4874]
actions = ["cham", "cnn", "dd", "float", "gzip", "hello", "image", "lin_pack", "train", "aes", "video", "json"]
tmp = pd.read_csv(os.path.join(path, base_file))
func_names = tmp["function"].unique()
for warm_time, k in zip(warm_times, actions):
  for name in func_names:
    if k in name:
      out.append((name,warm_time))
warm_times = pd.DataFrame(out,columns=['function',"warm"])
warm_times.index = warm_times['function']

def path_to_key(pth):
  # print(pth)
  parts = pth.split("/")
  # print(parts, [l for l in parts if "compare" in l])
  wanted = [l for l in parts if "compare" in l]
  if len(wanted) != 1:
    print("weird file path, please support!: {}".format(pth))
    raise Exception("Failure")
  return wanted[0][len("compare-"):]

def get_warm_times(df):
  warmed = df[df["cold"] == False]
  colded = df[df["cold"] == True]
  warm_means = warmed.groupby(['function'])["latency"].mean()
  # print(warm_means.isna())
  cold_means = colded.groupby(['function'])["latency"].mean()
  return warm_means, cold_means

def mean_lats_per_fn(expf):
  df = pd.read_csv(expf, header=0, usecols=["function", "cold", "latency", "activation_id"])
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
  return mean_warm
  #sum(mean_warm['Wnorm'])

def compare(numerator_str, denom_str, paths):
  numerator_paths = []
  # print("{}-{}".format(users, numerator_str))
  for pth in paths:
    if "{}-{}".format(users, numerator_str) in pth:
      # print(pth)
      numerator_paths.append(os.path.join(pth, base_file))
  # numerator_path = os.path.join(path, "{}-{}".format(users, numerator_str), base_file)
  # print(numerator_str)
  numerator=Wnorms(numerator_paths)
  # sum(bounded['Wnorm'])
  # print(numerator)
  # denom_path = os.path.join(path, "{}-{}".format(users, denom_str), base_file)
  denom_paths = []
  # print("{}-{}".format(users, denom_str))
  for pth in paths:
    if "{}-{}".format(users, denom_str) in pth:
      # print(pth)
      denom_paths.append(os.path.join(pth, base_file))
  # print(denom_str)
  denom=Wnorms(denom_paths)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)

  r2_ch_rl = numerator/denom
  # print(sorted(r2_ch_rl))
  ax.hlines(1.0, xmin=-0.1, xmax=len(r2_ch_rl)-.9, color='black')

  # ax.plot(sorted(r2_ch_rl),marker='o',alpha=0.3)

  ymin = []
  ymax = []
  for pt in sorted(r2_ch_rl):
    if pt <= 1:
      ymin.append(pt)
      ymax.append(1)
    else:
      ymin.append(1)
      ymax.append(pt)
  ax.vlines([i for i in range(len(ymin))],ymin,ymax)

  # ax.set_ylabel("Invoker {}".format(metric))
  ax.set_ylabel("Normalized latency")
  # ax.legend()
  # ax.set_yscale('log')
  ax.set_title("{} / {}".format(numerator_str, denom_str))
  save_fname = os.path.join("{}-compare-functions-{}-{}.png".format(users, numerator_str, denom_str))
  print(save_fname)
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

compare(shard_str, bound_str, args.path)
compare(shard_str, rand_str, args.path)
compare(bound_str, rand_str, args.path)
compare(rr_str, rand_str, args.path)
