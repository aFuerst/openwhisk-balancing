from collections import defaultdict
import os, argparse
from types import CoroutineType
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
parser.add_argument("--ceil", required=False, action='store_true')
args = parser.parse_args()

base_file = "parsed_successes.csv"
warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

min_warm_times = {}
for k in warm_results.keys():
  min_warm_times[k] = min(warm_results[k])

def load_warm_times(specific_funcs=None):
  i = 0
  path = os.path.join(args.path[i], "parsed_successes.csv")
  while not os.path.exists(path):
    i += 1
    path = os.path.join(args.path[i], "parsed_successes.csv")
    if i > len(args.path):
      raise Exception("could not find valid file")
  tmp = pd.read_csv(path)
  out = []
  chosen = tmp["function"].unique()
  if specific_funcs is not None:
    chosen = specific_funcs
  for k, warm_time in min_warm_times.items():
    for name in tmp["function"].unique():
      if specific_funcs is not None and name in specific_funcs:
        break
      if k in name:
        out.append((name,warm_time))
  warm_times = pd.DataFrame(out,columns=['function',"warm"])
  warm_times.index = warm_times['function']
  return warm_times

def path_to_lb(pth):
  parts = pth.split("/")
  if args.ceil:
    p = [p for p in parts if "compare-" in p][-1]
    return float(p.split("-")[-1])
  else:
    return parts[-1].split("-")[1]

def _apply_func_name(data, specific_funcs):
  name = data["function"]
  name = name.split("_")[0]
  return name in specific_funcs

def mean_lats_per_fn(expf, specific_funcs=None):
  df = pd.read_csv(expf, header=0, usecols=["function", "cold", "latency", "activation_id"])
  if specific_funcs is not None:
    filt = df.apply(func=_apply_func_name, args=(specific_funcs,), axis=1)
    # print(filt, len(df))
    df = df[filt]
    # print(len(df))
    # exit(0)
  ldf = df[['function', 'latency']]
  lgrps = ldf.groupby(['function'])
  #Also need the length of the list for correct normalization? 
  mean_lats = lgrps.mean()
  # print(mean_lats)
  return mean_lats, lgrps, ldf, df

def normalize_lats(expf, norm_by_cnt=False, specific_funcs=None):
  mean_lats, lgrps, ldf, df = mean_lats_per_fn(expf, specific_funcs)
  mean_warm = pd.Series(mean_lats['latency'], index=mean_lats.index)
  counts = lgrps['latency'].count()
  
  warm_times = load_warm_times(specific_funcs)
  norm_warm = pd.Series(mean_warm/warm_times['warm'], index=mean_warm.index)
  # print(warm_times)
  # print(norm_warm)
  # exit()
  if norm_by_cnt:
    C=sum(counts)
    norm_warm = pd.Series((norm_warm*counts)/C, index=mean_warm.index)
  return norm_warm

def get_norm_means(expfs, norm_by_cnt=False, specific_funcs=None):
  means = []
  for expf in expfs:
    norm_warm = normalize_lats(expf, norm_by_cnt, specific_funcs)
    means.append(norm_warm.mean())
  means = np.array(means)
  return means.mean(), means.std()

def plot(norm_by_cnt=False, specific_funcs=None, name=""):
  split_paths = defaultdict(list)

  for pth in args.path:
    if str(args.users) not in pth:
      continue
    lb = path_to_lb(pth)
    if args.ceil and os.path.exists(os.path.join(pth, base_file)):
      split_paths[lb].append(os.path.join(pth, base_file))
    else:
      if "{}-{}".format(args.users, lb) in pth and os.path.exists(os.path.join(pth, base_file)):
        split_paths[lb].append(os.path.join(pth, base_file))

  data = []
  stds = []
  for k in sorted(split_paths.keys()):
    norm_warm, std = get_norm_means(split_paths[k], norm_by_cnt, specific_funcs)
    # norm_warm = normalize_lats(split_paths[k], norm_by_cnt)
    data.append(norm_warm)
    stds.append(std)
  # print(data)
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer':'Bounded', 'RandomForwardLoadBalancer':'Random', 'RoundRobinLB':'RR', 
        'ShardingContainerPoolBalancer':'Sharding', 'GreedyBalancer':'Greedy', 'RandomLoadUpdateBalancer':'old_RLU',
            "EnhancedShardingContainerPoolBalancer":"Enhance", "RLUShardingBalancer":"RLU"}
  if args.ceil:
    labels = sorted(split_paths.keys())
  else:
    labels = [map_labs[x] for x in sorted(split_paths.keys())]

  ax.bar(labels, data, yerr=stds)

  if norm_by_cnt:
    save_fname = os.path.join("{}-global-latencies-cntnorm{}.pdf".format(args.users, name))
  else:
    save_fname = os.path.join("{}-global-latencies{}.pdf".format(args.users, name))
  ax.set_ylabel("Global Latency")
  if args.ceil:
    ax.set_xlabel("Bounded Load")
  else:
    ax.set_xlabel("LoadBalancing Policy")

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

plot(True)
plot(False)

slowest = sorted(min_warm_times.items(), key=lambda x: x[1])[-4:]
slowest = [s[0] for s in slowest]
fastest = sorted(min_warm_times.items(), key=lambda x: x[1])[:-4]
fastest = [f[0] for f in fastest]
assert len(slowest) + len(fastest) == len(min_warm_times)

plot(True, fastest, "-fast")
plot(True, slowest, "-slow")

plot(False, fastest, "-fast")
plot(False, slowest, "-slow")
