import os, sys, argparse
from datetime import datetime, timezone
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.use('Agg')
import matplotlib.pyplot as plt

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

def plot(path, metric):
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)
  time_min = datetime(2050, 1, 1, tzinfo=None)
  limit=datetime(1970, 1, 1, tzinfo=None)
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

          file_data.append(pack)
          # break
    df = pd.DataFrame.from_records(file_data, index="time")
    df = df[df["usedMem"] > 128.0]
    df = df.resample("S").mean().interpolate()
    ax.plot(df.index, df[metric], label=str(i)) #"Indexer: {}".format(i))
    limit = max(limit, df.index[-1])
    time_min = min(time_min, df.index[0])
    # print(df) #.describe())

  if "mem" in metric.lower():
    ax.hlines(40*1024, time_min, limit, color='red')
  ax.set_ylabel(metric)
  ax.set_xlabel("Time (sec)")
  # xticks = ax.get_xticks()
  # xticks /= 60
  # xticks = [round(x) for x in xticks]
  # print(xticks)
  ax.set_xticklabels(ax.get_xticks(), rotation=45, rotation_mode="anchor")
  ax.legend() # bbox_to_anchor=(1.6,.6), loc="right", columnspacing=1

  plt.savefig("{}-{}.png".format(users, metric), bbox_inches="tight")
  plt.close(fig)


for metric in ["loadAvg", "usedMem", "containerActiveMem"]:
  plot(path, metric=metric)
