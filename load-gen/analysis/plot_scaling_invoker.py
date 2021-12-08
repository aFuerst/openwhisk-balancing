import os, sys, argparse
from datetime import datetime, timezone
from numpy import dtype
import pandas as pd
import matplotlib as mpl
from collections import defaultdict

mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

path = "/extra/alfuerst/20min-scaling-10sec/0/50-RandomForwardLoadBalancer/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 50
if len(sys.argv) > 2:
  users = int(sys.argv[2])

sec_per_user = 10
if len(sys.argv) > 3:
  sec_per_user = int(sys.argv[3])

def date_idx_to_min(idx):
  return (idx.second + idx.minute*60) / 60

def extract_date(line):
  time, *_ = line.split(" ")
  time = time.strip('[]')
  return datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")

def plot(path, metric):
  metric, nice_name = metric
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)
  time_min=datetime(1970, 1, 1, tzinfo=None)
  colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
  mean_df = None
  save_pth = path

  invok_start_times = {}
  invok_loads = defaultdict(list)
  controller_file = os.path.join(path, "controller0_logs.log")
  with open(controller_file) as f:
    for line in f:
      if "Cont result" in line:
        # [2021-12-03T15:40:45.170Z] [INFO] [#tid_sid_invokerRedis] [RedisAwareLoadBalancerState] Cont result invoker4/4: Connected to v-021.victor.futuresystems.org
        invok_start_time = extract_date(line)

        marker = "Cont result "
        pos = line.find(marker)
        invoker_id_start = pos + len(marker)  # line[pos:len(marker)]
        invoker_id = line[invoker_id_start:].find(":")
        invoker_id = line[invoker_id_start: invoker_id_start +
                             invoker_id].strip()
        invok_start_times[invoker_id] = invok_start_time
      if "Current system data=" in line:
        line = line.strip()
        time = extract_date(line)
        marker = "minute Load Avg: Map("
        pos = line.find(marker)
        map_start = pos + len(marker)  # line[pos:len(marker)]
        map = line[map_start:].strip(")")
        map = map.split(",")
        if len(map) == 8:
          # print(len(map))
          invok_loads["time"].append(time)
          for pair in map:
            invoker, load = pair.split(" -> ")
            invoker = invoker.strip()
            invok_loads[invoker].append(float(load))
        # print(time, map)
  
  invoker_cols = [k for k in invok_loads.keys() if k != "time"]

  mean_df = pd.DataFrame.from_dict(invok_loads)
  mean_df.index = mean_df["time"]

  times = date_idx_to_min(mean_df.index)
  # print("times:", times[0])
  t_0 = times[0]
  times = times - t_0
  mean_df["present"] = mean_df[invoker_cols].notnull().sum(axis=1)
  mean_df["mean"] = mean_df[invoker_cols].sum(axis=1) / mean_df["present"]
  mean_df["std"] = mean_df[invoker_cols].std(axis=1)
  # print(invok_start_times.keys())

  for i, invoker in enumerate(invoker_cols):
    inv_ser = mean_df[invoker]
    if invoker in invok_start_times:
      inv_ser = inv_ser[inv_ser.index > invok_start_times[invoker]]
    xs = date_idx_to_min(inv_ser.index)
    # print("xs:", xs[0], xs[0]-t_0)
    xs = xs - t_0
    ax.plot(xs, inv_ser, label=str(i), color=colors[i])

  final_user_min = (users * sec_per_user) / 60
  print(final_user_min)
  ax.vlines(x=final_user_min, ymin=0, ymax=15, color='r')
  ax.text(final_user_min, 15, "Final User Created", verticalalignment='center')

  ax.plot(times, mean_df["mean"], label="Mean", color='k')
  ax.plot(times, mean_df["mean"]+mean_df["std"], label="mean std", color='k', linestyle='dashed')
  ax.plot(times, mean_df["mean"]-mean_df["std"], color='k', linestyle='dashed')

  ax.set_ylabel(nice_name)
  ax.set_xlabel("Time (min)")

  ax.legend(bbox_to_anchor=(1.6,.6), loc="right", columnspacing=1)

  save_fname = os.path.join(save_pth, "{}-{}.png".format(users, metric))
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

for metric in [("loadAvg", "Load Average")]:#  , ("usedMem", "Used Memory"), ("containerActiveMem", "Active Memory")]:
  plot(path, metric=metric)
