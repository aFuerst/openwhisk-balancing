import os, sys, argparse
from datetime import datetime, timezone
import pandas as pd

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

def plot(path):
  metric = "loadAvg"
  time_min = datetime(2050, 1, 1, tzinfo=None)
  limit=datetime(1970, 1, 1, tzinfo=None)
  colors = ["tab:blue", "tab:orange", "tab:green", "tab:red", "tab:purple", "tab:brown", "tab:pink", "tab:olive"]
  load_df = None
  save_pth = path

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
    limit = max(limit, df.index[-1])
    time_min = min(time_min, df.index[0])

    new_col = "{}_{}".format(i, metric)
    if load_df is None:
      renamed = df.rename(columns= {metric : new_col})

      load_df = renamed[[new_col]]
    else:
      renamed = df.rename(columns= {metric : new_col})
      load_df = load_df.join(renamed[[new_col]], how='outer', sort=True)

  load_df.fillna(0.3, inplace=True)
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
        pack["activation_id"] = activation_id

        controller_data.append(pack)

  # print(len(controller_data))
  # print(controller_data[10])
  # print(load_df["3_loadAvg"])
  df = pd.DataFrame.from_records(controller_data)#, index="time")
  # print(df.columns)
  df["time"] = df["time"].dt.round("1s")

  def get_load(data):
    # print(len(data), type(data), data["invoker"])
    invoker = "{}_{}".format(data["invoker"], metric)
    time = data["time"]
    # print("load:", load_df[invoker][time])
    return load_df[invoker][time]


  df["load"] = df.apply(get_load, axis=1)
  print(df)

plot(path)
