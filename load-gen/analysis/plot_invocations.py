import os, sys
from collections import defaultdict
import argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
parser.add_argument("--ceil", required=False, action='store_true')
args = parser.parse_args()

def date_idx_to_min(idx):
  return (idx.second + idx.minute*60) / 60

def path_to_lb(pth):
  # print(pth)
  parts = pth.split("/")
  # print(parts)

  if args.ceil:
    p = [p for p in parts if "compare-" in p][-1]
    return p.split("-")[-1]
  else:
    return parts[-1].split("-")[1]

def plot(paths, users):
  warm_dict = defaultdict(list)
  cold_dict = defaultdict(list)
  for path in paths:
    file = os.path.join(path, "controller0_logs.log")
    if not os.path.exists(file):
      continue
    if not str(users) + "-" in path:
      continue
    file = os.path.join(path, "controller0_logs.log")
    controller_data = []
    with open(file) as f:
      for line in f:
        if "scheduled activation" in line:
          # [2021-11-03T00:58:43.037Z] [INFO] [#tid_vXC1Z7nyawfi8qAc7IaSuBjZC2UAdxyh] [BoundedLoadsLoadBalancer] scheduled activation 9d024a94cf3243e1824a94cf3273e178, action 'afuerst/cnn_150@0.0.20', ns 'afuerst', mem limit 512 MB (std), time limit 300000 ms (non-std) to invoker0/0
          time = line[:len("[2021-11-03T00:58:43.037Z]")]
          time = time.strip('[]')
          parsedtime = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")

          # invoker = line[-(len("invoker0/0")+1):].strip()
          invoker = int(line[-2].strip())
          marker = "scheduled activation"
          pos = line.find(marker)
          activation_id_start = pos + len(marker) # line[pos:len(marker)]
          activation_id_end = line[activation_id_start:].find(",")
          activation_id = line[activation_id_start : activation_id_start + activation_id_end].strip()
          # print(activation_id_start, activation_id_end, line[activation_id_start:], activation_id)
          # break
          pack = {}
          pack["time"] = parsedtime
          pack["invoker"] = int(invoker)
          pack["activation_id"] = str(activation_id)

          controller_data.append(pack)

    # print(len(controller_data))
    # print(controller_data[10])
    # print(load_df["3_loadAvg"])
    df = pd.DataFrame.from_records(controller_data)#, index="time")
    # print(df.columns)
    df["time"] = df["time"].dt.round("20s")
    colors = ["tab:blue", "tab:orange", "tab:green", "tab:red",
              "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
    fig, ax = plt.subplots()
    plt.tight_layout()
    fig.set_size_inches(5, 3)

    for i, invoker in enumerate(sorted(df["invoker"].unique())):
      groups = df[df["invoker"] == invoker].groupby(["time"])
      data = []
      xs = []
      ys = []
      for g in groups:
        xs.append(date_idx_to_min(g[0]))
        ys.append(len(g[1]))
        data.append((g[0], len(g[1])))
      ax.plot(xs, ys, label=int(invoker), color=colors[i])
    save_fname = os.path.join(path, "{}-invokes.pdf".format(args.users))

    ax.set_ylabel("Invocations")
    ax.set_xlabel("Minute")
    ax.legend()
    print(save_fname)

    plt.savefig(save_fname, bbox_inches="tight")
    plt.close(fig)


plot(args.path, args.users)
