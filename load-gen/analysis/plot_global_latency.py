from collections import defaultdict
import os, argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import pickle

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

base_file = "parsed_successes.csv"
warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

min_warm_times = {}
for k in warm_results.keys():
  min_warm_times[k] = min(warm_results[k])

path = os.path.join(args.path[0], "parsed_successes.csv")
tmp = pd.read_csv(path)
out = []
func_names = tmp["function"].unique()
for k, warm_time in min_warm_times.items():
  for name in func_names:
    if k in name:
      out.append((name,warm_time))
warm_times = pd.DataFrame(out,columns=['function',"warm"])
warm_times.index = warm_times['function']

def path_to_lb(pth):
  parts = pth.split("/")
  return parts[-1].split("-")[1]


def mean_lats_per_fn(expf):
  df = pd.read_csv(expf, header=0, usecols=["function", "cold", "latency", "activation_id"])
  ldf = df[['function', 'latency']]
  lgrps = ldf.groupby(['function'])
  #Also need the length of the list for correct normalization? 
  mean_lats = lgrps.mean()
  return mean_lats, lgrps, ldf, df

def normalize_lats(expf, norm_by_cnt=False):
  mean_lats, lgrps, ldf, df = mean_lats_per_fn(expf)
  mean_warm = pd.Series(mean_lats['latency'], index=mean_lats.index)
  counts = lgrps['latency'].count()
  
  norm_warm = pd.Series(mean_warm/warm_times['warm'], index=mean_warm.index)
  if norm_by_cnt:
    C=sum(counts)
    norm_warm = pd.Series((norm_warm*counts)/C, index=mean_warm.index)
  return norm_warm

def get_norm_means(expfs, norm_by_cnt=False):
  means = []
  for expf in expfs:
    norm_warm = normalize_lats(expf, norm_by_cnt)
    means.append(norm_warm.mean())
  means = np.array(means)
  return means.mean(), means.std()

def plot(norm_by_cnt=False):
  split_paths = defaultdict(list)

  for pth in args.path:
    if str(args.users) not in pth:
      continue
    lb = path_to_lb(pth)
    if "{}-{}".format(args.users, lb) in pth and os.path.exists(os.path.join(pth, base_file)):
      split_paths[lb].append(os.path.join(pth, base_file))

  data = []
  stds = []
  for k in split_paths.keys():
    norm_warm, std = get_norm_means(split_paths[k], norm_by_cnt)
    # norm_warm = normalize_lats(split_paths[k], norm_by_cnt)
    data.append(norm_warm)
    stds.append(std)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer':'Bounded', 'RandomForwardLoadBalancer':'Random', 'RoundRobinLB':'RR', 'ShardingContainerPoolBalancer':'Sharding', 'RandomLoadUpdateBalancer':'RLU', 'GreedyBalancer':'Greedy'}
  labels = [map_labs[x] for x in sorted(split_paths.keys())]

  ax.bar(labels, data, yerr=stds)

  if norm_by_cnt:
    save_fname = os.path.join("{}-global-latencies-cntnorm.pdf".format(args.users))
  else:
    save_fname = os.path.join("{}-global-latencies.pdf".format(args.users))
  ax.set_ylabel("Global Latency")
  ax.set_xlabel("LoadBalancing Policy")

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

plot(True)
plot(False)