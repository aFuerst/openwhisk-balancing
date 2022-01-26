import os, sys
from collections import defaultdict
import argparse
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import pickle

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--ttl", nargs='+', required=True)
parser.add_argument("--balancers", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

min_warm_times = {}
for k in warm_results.keys():
  min_warm_times[k] = min(warm_results[k])

tmp = None
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

def path_to_key(pth):
  # print(pth)
  parts = pth.split("/")
  # print(parts, [l for l in parts if "compare" in l])
  wanted = [l for l in parts if "compare" in l]
  if len(wanted) != 1:
    print("weird file path, please support!: {}".format(pth))
    raise Exception("Failure")
  return float(wanted[0][len("compare-"):])

def plot(paths, users, warm, ttls):
  mean_sums = defaultdict(int)
  df_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if str(users) + "-" not in pth:
      continue
    df = pd.read_csv(file)
    if warm:
      df = df[df["cold"] == False]
    grouped = df.groupby(by="function")
    for name, group in sorted(grouped, key=lambda p: float(p[0].split("_")[-1])):
      mean_sums[name] += group["latency"].mean()
    df_dict[path_to_key(pth)].append(df)

  for pth in ttls:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if str(users) + "-" not in pth:
      continue
    df = pd.read_csv(file)
    if warm:
      df = df[df["cold"] == False]
    grouped = df.groupby(by="function")
    for name, group in sorted(grouped, key=lambda p: float(p[0].split("_")[-1])):
      mean_sums[name] += group["latency"].mean()
    df_dict["TTL"].append(df)

  for name in mean_sums.keys():
    mean_sums[name] = mean_sums[name] / len(paths)

  tputs = []
  colds = []
  pts = []
  labels = []
  for key in sorted(df_dict.keys()):
    box_pts = []
    dfs = df_dict[key]
    tput = 0
    cold = 0

    data = defaultdict(float)
    for df in dfs:
      tput += len(df)
      cold += len(df[df["cold"] == True])

      grouped = df.groupby(by="function")
      for name, group in grouped:
        data[name] += group["latency"].mean()

    for name in data.keys():
      data[name] /= (len(dfs) * float(warm_times[warm_times['function'] == name]['warm']))
    # print(sorted(data.items(), key=lambda x: x[0]))
    # return
    pts.append(list(data.values()))
    # pts.append(box_pts)
    labels.append(key)
    tputs.append(tput / len(dfs))
    colds.append(cold / len(dfs))

  fig, ax = plt.subplots()
  ax2 = ax.twinx()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer': 'CH-BL', 'RandomForwardLoadBalancer': 'Random', 'RoundRobinLB': 'RR', 'ShardingContainerPoolBalancer': 'OW+GD',
              'GreedyBalancer': 'Greedy', 'RandomLoadUpdateBalancer': 'old_RLU', 'TTL': 'OW+TTL',
              "EnhancedShardingContainerPoolBalancer": "Enhance", "RLUShardingBalancer": "RLU_shard", "LeastLoadBalancer": "LL",
              "RLULFSharding": "RLU"}
  labels = [map_labs[x] for x in labels]

  poss = [2*i for i in range(len(pts))]
  ax.boxplot(pts, labels=labels, positions=poss, showfliers=False)
  # ax.set_yscale('log')
  handles = []
  leg_labels=[]
  ax2.plot(poss, tputs, 'o', color="tab:red")
  handles.append(mpatches.Patch(color="tab:red", label='All Invokes'))

  leg_labels.append("All Invokes")
  if not warm:
    ax2.plot(poss, colds, 'o', color="tab:blue")
    handles.append(mpatches.Patch(color="tab:blue", label='Cold starts'))
    leg_labels.append("Cold starts")

  plt.xticks(rotation=90)
  ax.set_ylabel("Normalized latency")
  ax2.set_ylabel("Served functions")

  if warm:
    save_fname = os.path.join("{}-compare-overload-warm.pdf".format(args.users))
  else:
    save_fname = os.path.join("{}-compare-overload.pdf".format(args.users))

  ax.legend(handles=handles, labels=leg_labels)
  print(save_fname)

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


plot(args.path, args.users, warm=False)
plot(args.path, args.users, warm=True)
