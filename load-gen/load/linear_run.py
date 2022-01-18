from wsk_interact import *
import os
from time import time, sleep
from collections import defaultdict
import pickle
from concurrent.futures import ThreadPoolExecutor
# import pandas as pd

host="https://172.29.200.161:10001"
auth="e0ddac86-ac5a-45e0-bf37-ec3dcf3f70de:WwX7nwMvLWHQhW2vjZtyZkL8QVTcKa4PplCp2riFYn49TnBogJb21V09EcEzIw2D"

pool = ThreadPoolExecutor(max_workers=3)
set_properties(host=host, auth=auth)
class Action:
  def __init__(self, name, url, warmtime, coldtime):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime

action_dict = {}

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  path = os.path.join("../ow-actions", zip_file)
  url = add_web_action(action_name, path, container, memory=memory, host=host)
  action_dict[action_name] = Action(action_name, url, warm_time, cold_time)

cold_results = defaultdict(list)
warm_results = defaultdict(list)

for name, action in action_dict.items():
  print(name)
  while len(warm_results[name]) < 15:
    # futures = []
    # for i in range(6):
    #   future = invoke_web_action_async(action.url, pool, auth, host)
    #   futures.append((action, future))
    # for action, future in futures:
    #   was_cold, latency, ret_json, activation_id = future.result()
    #   if was_cold == True:
    #     cold_results[name].append(latency)
    #   elif was_cold == False:
    #     warm_results[name].append(latency)
    #   else:
    #     pass

    start = time()
    r = requests.get(action.url, verify=False)
    latency = time() - start
    ret_json = r.json()
    if "cold" in ret_json:
        if ret_json["cold"]:
          cold_results[name].append(latency)
        else:
          warm_results[name].append(latency)
    else:
      print("weird json:", ret_json)
for k in warm_results.keys():
  print("{} warm results, avg = {}; min = {}".format(k, sum(warm_results[k]) / len(warm_results[k]), min(warm_results[k])))
  # if len(cold_results[k]) > 0:
  #   print("cold results, avg = {}; min = {}".format(k), sum(cold_results[k]) / len(cold_results[k]), min(cold_results[k]))

with open("warmdata_16.pckl", "w+b") as f:
  pickle.dump(warm_results, f)

# df = pd.DataFrame.from_records(data, columns=[func, "was_cold", "latency"])
# df.to_csv("run.csv")


