import matplotlib.pyplot as plt
import os
import sys
import argparse
from datetime import datetime, timezone
from numpy import dtype
import pandas as pd
from pathlib import Path
import matplotlib as mpl
mpl.rcParams.update({'font.size': 12})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=120, required=False)
parser.add_argument("--ttl", nargs='+', required=True)
parser.add_argument("--balancers", nargs='+', required=True)
args = parser.parse_args()

def path_to_lb(pth):
  parts = pth.strip("/").split("/")
  return parts[-1].split("-")[-1]

def date_idx_to_min(idx):
  ret = (idx.second + idx.minute*60) / 60
  return ret - min(ret) 

def invoker_load_df(path, metric):
  mean_df = None
  time_min = datetime(1970, 1, 1, tzinfo=None)
  invoker_cols = []

  for i in range(8):
    file = os.path.join(path, "invoker{}_logs.log".format(i))
    file_data = []
    if os.path.exists(file):
      with open(file) as f:
        for line in f:
          if "Updated data in Redis data" in line:
            time, *_, data = line.split(" ")

            # {"containerActiveMem":0.0,"cpuLoad":-1.0,"loadAvg":0.5,"priorities":[["whisk.system/invokerHealthTestAction0",0.0,2650.0]],"running":0.0,"runningAndQ":0.0,"usedMem":128.0}
            data = data.strip().strip('{}')
            time = time.strip('[]')

            pack = {}
            for pair in data.split(","):
              if ':' in pair and "priorities" not in pair:
                key, val = pair.split(":")
                key = key.strip("\"")
                pack[key] = float(val)

            # [2021-10-28T13:43:28.907Z]
            parsedtime = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
            pack["time"] = parsedtime
            pack["vm_cpu"] = pack["us"] + pack["sy"]

            file_data.append(pack)
            # break
      df = pd.DataFrame.from_records(file_data, index="time")
      temp = df[df["usedMem"] > 128.0]
      if len(temp) != 0:
        df = temp
      else:
        print("!!!no times had usedMem above 128!!!", file)

      df = df.resample("S").mean().interpolate()
      df.index = df.index - (df.index[0] - time_min)
      xs = date_idx_to_min(df.index)
      if metric == "loadAvg":
        df[metric] = df[metric] / 16

      new_col = "{}_{}".format(i, metric)
      invoker_cols.append(new_col)
      if mean_df is None:
        renamed = df.rename(columns={metric: new_col})

        mean_df = renamed[[new_col]]
      else:
        renamed = df.rename(columns={metric: new_col})
        mean_df = mean_df.join(renamed[[new_col]])

  if mean_df is None:
    return None

  times = date_idx_to_min(mean_df.index)
  mean_df["time"] = times
  mean_df["present"] = mean_df[invoker_cols].notnull().sum(axis=1)
  mean_df["mean"] = mean_df[invoker_cols].sum(axis=1) / mean_df["present"]
  mean_df["std"] = mean_df[invoker_cols].std(axis=1)
  mean_df["var"] = mean_df[invoker_cols].var(axis=1)
  return mean_df

def plot(paths, metric):
  metric, nice_name = metric
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)
  colors = ["tab:blue", "tab:orange", "tab:green", "tab:red",
            "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
  map_labs = {'BoundedLoadsLoadBalancer': 'CH-BL', 'RandomForwardLoadBalancer': 'Random', 'RoundRobinLB': 'RR',
              'ShardingContainerPoolBalancer': 'OW+GD', 'GreedyBalancer': 'Greedy', 'RandomLoadUpdateBalancer': 'old_RLU',
              "EnhancedShardingContainerPoolBalancer": "Enhance", "RLULFSharding": "RLU", "LeastLoadBalancer":"LL",
              "TTL":"OW+TTL"}

  for path in paths:
    lb = path_to_lb(path)
    file = os.path.join(path, "controller0_logs.log")
    if lb not in args.balancers:
      continue
    if not os.path.exists(file):
      continue
    if not "/"+str(args.users) + "-" + lb in path:
      continue
    # print(path)
    mean_df = invoker_load_df(path, metric)

    label = map_labs[lb]
    ax.plot(mean_df['time'], mean_df["var"], label=label)

  for path in args.ttl:
    lb = "TTL"
    file = os.path.join(path, "controller0_logs.log")
    if not os.path.exists(file):
      continue
    if not "/"+str(args.users) + "-ShardingContainerPoolBalancer" in path:
      continue
    mean_df = invoker_load_df(path, metric)
    label = map_labs[lb]
    ax.plot(mean_df['time'], mean_df["var"], label=label)


  if "mem" in metric.lower():
    ax.set_yscale('log')
  ax.set_ylabel("{} Variance".format(nice_name))
  ax.set_xlabel("Time (min)")
  ax.legend()  # bbox_to_anchor=(1.6,.6), loc="right", columnspacing=1

  save_pth = Path(paths[0]).parent.absolute()
  save_fname = os.path.join(save_pth, "{}-{}-variance.pdf".format(args.users, metric))
  # print(save_fname)
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


for metric in [("loadAvg", "Load"), ("usedMem", "Used Memory"), ("containerActiveMem", "Active Memory")]:
  plot(args.path, metric=metric)
