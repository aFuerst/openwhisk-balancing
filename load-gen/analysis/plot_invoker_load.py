import os, sys, argparse
from datetime import datetime, timezone
from numpy import dtype
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

def date_idx_to_min(idx):
  return (idx.second + idx.minute*60) / 60

def plot(path, metric):
  metric, nice_name = metric
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)
  time_min=datetime(1970, 1, 1, tzinfo=None)
  colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
  mean_df = None
  save_pth = path

  invoker_cols = []

  for i in range(8):
    file = os.path.join(path, "invoker{}_logs.log".format(i))
    file_data = []
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
    df = df[df["usedMem"] > 128.0]
    df = df.resample("S").mean().interpolate()
    df.index = df.index - (df.index[0] - time_min)
    xs = date_idx_to_min(df.index)
    if metric == "loadAvg":
      df[metric] = df[metric] / 16
    ax.plot(xs, df[metric], label=str(i), color=colors[i]) #"Indexer: {}".format(i))
    # limit = max(limit, df.index[-1])
    # time_min = min(time_min, df.index[0])
    # print(df) #.describe())

    # print(mean_df)
    new_col = "{}_{}".format(i, metric)
    invoker_cols.append(new_col)
    if mean_df is None:
      renamed = df.rename(columns= {metric : new_col})

      mean_df = renamed[[new_col]]
    else:
      renamed = df.rename(columns= {metric : new_col})
      mean_df = mean_df.join(renamed[[new_col]])

  times = date_idx_to_min(mean_df.index)
  if "mem" in metric.lower():
    ax.hlines(32*1024, times[0], times[-1], color='red')
  mean_df["present"] = mean_df[invoker_cols].notnull().sum(axis=1)
  mean_df["mean"] = mean_df[invoker_cols].sum(axis=1) / mean_df["present"]
  mean_df["std"] = mean_df[invoker_cols].std(axis=1)
  mean_df["var"] = mean_df[invoker_cols].var(axis=1)

  ax.plot(times, mean_df["mean"], label="Mean", color='k')
  # if metric != "vm_cpu":
  #   ax.plot(times, mean_df["var"], color='k', linestyle='dashed', label='Variance')

  # ax.plot(times, mean_df["mean"]+mean_df["std"], label="mean std", color='k', linestyle='dashed')
  # ax.plot(times, mean_df["mean"]-mean_df["std"], color='k', linestyle='dashed')

  ax.set_ylabel(nice_name)
  ax.set_xlabel("Time (min)")
  # xticks = ax.get_xticks()
  # xticks /= 60
  # xticks = [round(x) for x in xticks]
  # print(xticks)
  # ax.set_xticklabels(ax.get_xticks(), rotation=45, rotation_mode="anchor")
  ax.legend() # bbox_to_anchor=(1.6,.6), loc="right", columnspacing=1

  save_fname = os.path.join(save_pth, "{}-{}.pdf".format(users, metric))
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)
  # print(save_fname)

  if metric == "loadAvg":
    fig, ax = plt.subplots()
    plt.tight_layout()
    fig.set_size_inches(5,3)
    
    file = os.path.join(path, "parsed_successes.csv")
    def convert(t):
      # 2021-11-01 09:16:35
      return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")

    df = pd.read_csv(file, index_col="start_time", converters={"start_time":convert})
    df["duration"] = df["duration"] / 1000.0
    grouped = df.groupby(by="function")

    for name, group in grouped:
      if "150" in name:
        group = group[group["cold"] == False]
        normed = group["latency"] / group["latency"].mean()
        normed = normed.sort_index()
        min_t = min(normed.index)
        max_t = max(normed.index)
        # if name == "json_100":
        #   print(min_t, max_t)
        normed.index -= min_t
        ax.plot(normed, 'o')

    means = grouped[["duration", "latency"]].mean()

    func_time_split = df["transaction_name"].apply(str.split, args=("-")).to_list()

    min_t = min(mean_df.index)
    max_t = max(mean_df.index)
    mean_df.index -= min_t 
    # print(min_t, max_t)
    # print(metric, mean_df.columns)
    ax.plot(times, mean_df["mean"], label="Mean Load", color='k')
    ax.legend()
    save_fname = os.path.join(save_pth, "{}-{}.pdf".format(users, "load_vs_latency"))
    plt.savefig(save_fname, bbox_inches="tight")
    plt.close(fig)

for metric in [("loadAvg", "Load"), ("usedMem", "Used Memory"), ("containerActiveMem", "Active Memory"), ("vm_cpu", "CPU")]:
  plot(path, metric=metric)
