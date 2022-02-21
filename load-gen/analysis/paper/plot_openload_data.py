import matplotlib.pyplot as plt
import os, pickle
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


class Action:
  def __init__(self, name, url, warmtime, coldtime, freq_class):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime
    self.freq_class = freq_class

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
args = parser.parse_args()


def path_to_lb(pth):
  # print(pth)
  parts = pth.strip("/").split("/")
  return parts[-1]


def load_data(paths):
  warm_dict = defaultdict(lambda: defaultdict(list))
  cold_dict = defaultdict(lambda: defaultdict(list))
  none_dict = defaultdict(lambda: defaultdict(list))
  dropped_dict = defaultdict(list)
  lb_cnts = defaultdict(int)
  found = 0
  expected = 0
  for pth in paths:
    file = os.path.join(pth, "data.pckl")
    if not os.path.exists(file):
      continue
    with open(file, "r+b") as f:
      data = pickle.load(f)
      cld = 0
      wrm = 0
      lb_cnts[path_to_lb(pth)] += 1
      for action_name, was_cold, latency, *_ in data:
        # print(action.name, was_cold, latency)
        if was_cold == True:
          cold_dict[path_to_lb(pth)][action_name].append(latency)
          cld += 1
        elif was_cold == False:
          warm_dict[path_to_lb(pth)][action_name].append(latency)
          wrm += 1
        else:
          none_dict[path_to_lb(pth)][action_name].append(latency)
      trace_file = os.path.join(pth, "trace.pckl")
      with open(trace_file, "r+b") as f:
        data = pickle.load(f)
        expected = len(data)
        found = wrm + cld
        dropped_dict[path_to_lb(pth)].append(expected - found)
        # print(len(data))
  # for lb in warm_dict.keys():
  #   found = sum([len(lst) for lst in warm_dict[lb].values()]) + \
  #       sum([len(lst) for lst in cold_dict[lb].values()])
  #   dropped = (expected//2) - found
  #   dropped_dict[lb] = dropped
    # print(lb, dropped)
  return warm_dict, cold_dict, none_dict, lb_cnts, dropped_dict

def plot_tput(paths):
  warm_dict, cold_dict, none_dict, lb_cnts, dropped_dict = load_data(paths)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer': 'CH-BL', 'RandomForwardLoadBalancer': 'Random', 'RoundRobinLB': 'RR',
                'ShardingContainerPoolBalancer': 'OW+GD', 'GreedyBalancer': 'Greedy', 'RandomLoadUpdateBalancer': 'old_RLU',
                "EnhancedShardingContainerPoolBalancer": "Enhance", "RLULFSharding": "RLU", "LeastLoadBalancer":"LL"}
  labels = [map_labs[x] for x in sorted(warm_dict.keys())]

  colds = []
  colds_std = []
  warms = []
  warms_std = []
  nones = []
  nones_std = []

  for lb in sorted(warm_dict.keys()):
    warms.append(sum([len(lst) for lst in warm_dict[lb].values()]) / lb_cnts[lb])
    warms_std.append(np.std([len(lst) for lst in warm_dict[lb].values()]))
    
    colds.append(sum([len(lst) for lst in cold_dict[lb].values()]) / lb_cnts[lb])
    colds_std.append(np.std([len(lst) for lst in cold_dict[lb].values()]))

    # nones.append(sum([len(lst) for lst in none_dict[lb].values()]) / lb_cnts[lb])
    nones.append(sum(dropped_dict[lb]) / lb_cnts[lb])
    nones_std.append(np.std(dropped_dict[lb]))

  print(labels)

  ax.bar(labels, colds, label="Cold", yerr=colds_std, color="tab:blue", error_kw=dict(ecolor='dimgray'))
  print(colds)

  ax.bar(labels, warms, bottom=colds, label="Warm", yerr=warms_std, color="tab:orange", error_kw=dict(ecolor='dimgray'))
  print(warms)

  nones_bottom = np.array(colds) + np.array(warms)
  ax.bar(labels, nones, bottom=nones_bottom, label="Dropped", color="black", error_kw=dict(ecolor='dimgray'))
  print(nones)
  # ax.hlines(9582, xmin=-1, xmax=2, color="red")

  save_fname = os.path.join("openload/openload-throughputs.pdf")
  ax.set_ylabel("Invocations")
  ax.set_xlabel("LoadBalancing Policy")
  ax.legend()

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


def load_warm_times(path, warm_dict, specific_funcs=None):
  warm_results = None
  with open("../load/warmdata_16.pckl", "r+b") as f:
    warm_results = pickle.load(f)

  min_warm_times = {}
  for k in warm_results.keys():
    min_warm_times[k] = min(warm_results[k])

  out = []
  sample = list(warm_dict.keys())[0]
  chosen = warm_dict[sample].keys()
  if specific_funcs is not None:
    chosen = specific_funcs
  for k, warm_time in min_warm_times.items():
    for name in warm_dict[sample].keys():
      if specific_funcs is not None and name in specific_funcs:
        break
      if k in name:
        out.append((name, warm_time))
  warm_times = pd.DataFrame(out, columns=['function', "warm"])
  warm_times.index = warm_times['function']
  return warm_times


def get_norm_means(paths, norm_by_cnt, specific_funcs=None):
  means = []
  for path in paths:
    warm_dict, cold_dict, none_dict, lb_cnts, dropped_dict = load_data([path])
    warm_times = load_warm_times(path, warm_dict)

    for key in warm_dict.keys():
      mean_lats = []
      for func in warm_dict[key].keys():
        latencies = [] + warm_dict[key][func]
        latencies += cold_dict[key][func]
        mean_lats.append((func, np.mean(latencies), len(latencies)))

      df = pd.DataFrame.from_records(
          mean_lats, columns=["function", "mean_lat", "count"])
      df.index = df["function"]
      norm_warm = pd.Series(df["mean_lat"]/warm_times['warm'], index=df.index)

      if norm_by_cnt:
        C = sum(df["count"])
        norm_warm = pd.Series((norm_warm*df["count"])/C, index=df.index)

    means.append(norm_warm.mean())
  means = np.array(means)
  mean, std = means.mean(), means.std()
  if norm_by_cnt:
    mean *= 100
    std *= 100
  return mean, std

def plot_latencies(paths, norm_by_cnt=False):
  split_paths = defaultdict(list)

  for pth in paths:
    lb = path_to_lb(pth)
    if os.path.exists(os.path.join(pth, "data.pckl")):
      split_paths[lb].append(pth)

  data = []
  stds = []
  for k in sorted(split_paths.keys()):
    norm_warm, std = get_norm_means(split_paths[k], norm_by_cnt=norm_by_cnt)
    data.append(norm_warm)
    stds.append(std)

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  map_labs = {'BoundedLoadsLoadBalancer': 'CH-BL', 'RandomForwardLoadBalancer': 'Random', 'RoundRobinLB': 'RR',
                'ShardingContainerPoolBalancer': 'OW+GD', 'GreedyBalancer': 'Greedy', 'RandomLoadUpdateBalancer': 'old_RLU',
                "EnhancedShardingContainerPoolBalancer": "Enhance", "RLULFSharding": "RLU", "LeastLoadBalancer":"LL"}
  labels = [map_labs[x] for x in sorted(split_paths.keys())]

  print(labels)
  print(data)
  ax.bar(labels, data, yerr=stds, color="firebrick")

  if norm_by_cnt:
    save_fname = os.path.join("openload/openload-latencies-cntnorm.pdf")
  else:
    save_fname = os.path.join("openload/openload-latencies.pdf")

  ax.set_ylabel("Global Latency Increase %")
  ax.set_xlabel("LoadBalancing Policy")

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

print(args.path)
plot_tput(args.path)
plot_latencies(args.path, False)
plot_latencies(args.path, True)
