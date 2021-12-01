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

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/compare/"
path = sys.argv[1]
count = int(sys.argv[2])

rand_str = "RandomForwardLoadBalancer"
bound_str = "BoundedLoadsLoadBalancer"
rr_str = "RoundRobinLB"
shard_str = "ShardingContainerPoolBalancer"

base_file = "parsed_successes.csv"

out=[]
# warm_times = [0.055, 1.939, 1.184, 0.044, 0.352, 0.034, 6.365, 0.049, 8.357, 0.633, 7.0, 0.279]
# actions = ["cham", "cnn", "dd", "float", "gzip", "hello", "image", "lin_pack", "train", "aes", "video", "json"]
# tmp = pd.read_csv(os.path.join(path, "{}-{}".format(count, bound_str), base_file))
# func_names = tmp["function"].unique()
# for warm_time, k in zip(warm_times, actions):
#   for name in func_names:
#     if k in name:
#       out.append((name,warm_time))
# warm_times = pd.DataFrame(out,columns=['function',"warm"])

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

def Wnorms(expf):
    mean_lats, lgrps, ldf, df = mean_lats_per_fn(expf)
    warm_times, cold_times = get_warm_times(df)
    mean_lats["warm"] = warm_times
    # mean_lats["colded"] = cold_times
    # print(warm_times)
    mean_warm = mean_lats
    # mean_warm = mean_lats.merge(warm_times,on='function')
    # print(mean_warm)
    mean_warm['norm'] = pd.Series(mean_warm['latency']/mean_warm['warm'], index=mean_warm.index)
    cold_norm = pd.Series(mean_warm['latency']/cold_times, index=mean_warm.index)
    nans = mean_warm['norm'].isna()
    # print(cold_norm)
    # print(mean_warm['norm'])
    mean_warm['norm'].fillna(cold_norm, inplace=True)
    # print(mean_warm['norm'])

    counts = lgrps.count()
    counts = counts.rename(columns={'latency':'counts'})
    mean_warm = mean_warm.merge(counts, on='function')
    C=sum(mean_warm['counts'])
    mean_warm['Wnorm']=pd.Series(mean_warm['norm']*mean_warm['counts']/C, index=mean_warm.index)
    
    return mean_warm
    #sum(mean_warm['Wnorm'])

def compare(numerator_str, denom_str):
  numerator_path = os.path.join(path, "{}-{}".format(count, numerator_str), base_file)
  numerator=Wnorms(numerator_path)
  # sum(bounded['Wnorm'])
  # print(numerator)
  denom_path = os.path.join(path, "{}-{}".format(count, denom_str), base_file)
  denom=Wnorms(denom_path)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)

  r2_ch_rl = numerator['Wnorm']/denom['Wnorm']
  # print(r2_ch_rl)
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
  # ax.set_xlabel("Normalized latency")
  # ax.legend()
  ax.set_title("{} / {}".format(numerator_str, denom_str))
  save_fname = os.path.join(path, "{}-compare-functions-{}-{}.png".format(count, numerator_str, denom_str))
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

compare(shard_str, bound_str)
compare(shard_str, rand_str)
compare(bound_str, rand_str)
compare(rr_str, rand_str)
