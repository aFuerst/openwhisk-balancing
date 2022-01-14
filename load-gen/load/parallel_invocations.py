from wsk_interact import *
import os
from time import time, sleep
from collections import defaultdict
import pickle
from concurrent.futures import ThreadPoolExecutor
import json
# import pandas as pd

host="https://172.29.200.161:10001"
auth="fd7a1d63-0944-45c6-9578-15bc7048031e:UXx4vs0BXnDrlnJiBTHp0fn9kMtyWTWQJBFLWdb62rSkixwkSE748RSkOT7ReoTp"

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

results = defaultdict(lambda: defaultdict(list))

for name, action in action_dict.items():
  print(name)
  for i in range(1,20):
    for repeats in range(3):
      futures = []
      for j in range(i):
        future = invoke_web_action_async(action.url, pool, auth, host)
        futures.append((action, future))
      for action, future in futures:
        data = future.result()
        results[name][i].append(data)

# for k in results.keys():
#   print("{} warm results, avg = {}; min = {}".format(k, sum(results[k]) / len(results[k]), min(results[k])))
#   # if len(cold_results[k]) > 0:
#   #   print("cold results, avg = {}; min = {}".format(k), sum(cold_results[k]) / len(cold_results[k]), min(cold_results[k]))

with open("parallel_invokes.pckl", "w+b") as f:
  results = json.loads(json.dumps(results))
  pickle.dump(results, f)

# df = pd.DataFrame.from_records(data, columns=[func, "was_cold", "latency"])
# df.to_csv("run.csv")


