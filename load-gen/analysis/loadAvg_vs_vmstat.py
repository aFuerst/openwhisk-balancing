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

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

def map_load(path, metrics="loadAvg"):
  time_min = datetime(2050, 1, 1, tzinfo=None)
  limit=datetime(1970, 1, 1, tzinfo=None)
  colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
  load_df = None
  

  for i in range(8):
    first_time = None
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
          pack["loadAvg"] /= 4
          pack["loadAvg"] *= 100
          pack["vm-cpu"] = (pack["us"] + pack["sy"]) / 1

          # [2021-10-28T13:43:28.907Z]
          parsedtime = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
          pack["time"] = parsedtime

          file_data.append(pack)
          # break
    df = pd.DataFrame.from_records(file_data)
    df["time"] = pd.to_datetime(df["time"])
    df.index = df["time"]
    df = df[df["usedMem"] > 128.0]
    df = df.resample("1s").mean().interpolate()
    df.index = df.index - (df.index[0] - time_min)
    # limit = max(limit, df.index[-1])
    # time_min = min(time_min, df.index[0])

    # print("invoker {}".format(i), df.index[0], df.index[-1])
    for metric in metrics:
      new_col = "{}_{}".format(i, metric)
      if load_df is None:
        renamed = df.rename(columns= {metric : new_col})

        load_df = renamed[[new_col]]
      else:
        renamed = df.rename(columns= {metric : new_col})
        load_df = load_df.join(renamed[[new_col]], how='outer', sort=True)

  # load_df.fillna(0.3, inplace=True)
  load_df.fillna(method='ffill', inplace=True)
  load_df.fillna(method='bfill', inplace=True)
  return load_df
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
        pack["invoker"] = invoker
        pack["activation_id"] = str(activation_id)

        controller_data.append(pack)

  # print(len(controller_data))
  # print(controller_data[10])
  # print(load_df["3_loadAvg"])
  df = pd.DataFrame.from_records(controller_data)#, index="time")
  # print(df.columns)
  df["time"] = df["time"].dt.round("1s")
  df["time"] = df["time"] - (df["time"][0] - time_min)

  def get_load(data):
    # print(len(data), type(data), data["invoker"])
    invoker = "{}_{}".format(data["invoker"], metric)
    time = data["time"]
    # print("load:", load_df[invoker][time])
    if time not in load_df[invoker]:
      if time < load_df[invoker].index[0]:
        # print("before", time - load_df[invoker].index[0])
        return load_df[invoker][0]
      if time > load_df[invoker].index[-1]:
        # print("after", time - load_df[invoker].index[-1])
        return load_df[invoker][-1]
      # print(time)
      # print(load_df[invoker])
    try:
      ret = load_df[invoker][time]
    except Exception as e:
      # print(load_df[invoker].index)
      delta = 1
      while (time - timedelta(seconds=delta)) not in load_df[invoker].index:
        delta += 1
      print(delta)
      delta = 1
      while (time + timedelta(seconds=delta)) not in load_df[invoker].index:
        delta += 1
      print(delta)
      print(invoker, time, (time - timedelta(seconds=1)), (time - timedelta(seconds=1)) in load_df[invoker].index, load_df[invoker].index[0], load_df[invoker].index[-1])
      raise e
    return ret


  df["load"] = df.apply(get_load, axis=1)
  # print(df)
  save_pth = os.path.join(path, "invokerload.csv")
  # for invok in df["invoker"].unique():
  #   print(invok, df[df["invoker"] == invok]["load"].max())
  df.to_csv(save_pth, index=False)
  return df

def date_idx_to_min(idx):
  mins = (idx.second + idx.minute*60)# + idx.hour*60*60)
  # mins -= 60*60
  return mins / 60

def plot_relationship(load_df, metrics):
  line_fmts = ['-', '--']
  colors = ['maroon', 'orange', 'green', 'navy', 'darkviolet', 'deeppink', 'crimson', 'steelblue']
  for invoker in range(8):
    fig, ax = plt.subplots()
    plt.tight_layout()
    fig.set_size_inches(5,3)

    for i, metric in enumerate(metrics):
      column = "{}_{}".format(invoker, metric)
      ax.plot(date_idx_to_min(load_df.index), load_df[column], line_fmts[i], label=metric)
  # ax.set_ylabel("Invoker {}".format(metric))
    ax.set_title("Invoker {}".format(invoker))
    ax.set_xlabel("Time")
    ax.legend()
    save_fname = os.path.join(path, "i{}-{}-vs-{}.png".format(invoker, metrics[0], metrics[1]))
    plt.savefig(save_fname, bbox_inches="tight")
    plt.close(fig)

metrics=["loadAvg", "vm-cpu"]
load_df = map_load(path, metrics=metrics)
plot_relationship(load_df, metrics)
