from wsk_interact import *
import os
from time import time, sleep
from collections import defaultdict
import pickle
from concurrent.futures import ThreadPoolExecutor
import json
# import pandas as pd

host="https://172.29.200.161:10001"
auth="5e9fb463-3082-4fce-847b-dbc17a7fbfa0:AZcoEhmD4dMsFTu7SPOAI4NkyDqtyaqkbxyud5bnMW5MssmPtQoC9BggNweGcJIj"

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
  for i in range(1,30):
    for repeats in range(3):
      futures = []
      for j in range(i):
        future = invoke_web_action_async(action.url, pool, auth, host)
        futures.append((action, future))
      for action, future in futures:
        data = future.result()
        results[name][i].append(data)

with open("warm_parallel_invokes.pckl", "w+b") as f:
  results = json.loads(json.dumps(results))
  pickle.dump(results, f)

#############################################################################

results = defaultdict(lambda: defaultdict(list))

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  print(action_name)
  path = os.path.join("../ow-actions", zip_file)

  for i in range(1, 30):
    for repeats in range(3):
      # new upload forces cold starts by preventing old conatiner reuse
      url = add_web_action(action_name, path, container, memory=memory, host=host)
      action = Action(action_name, url, warm_time, cold_time)

      futures = []
      for j in range(i):
        future = invoke_web_action_async(action.url, pool, auth, host)
        futures.append((action, future))
      for action, future in futures:
        data = future.result()
        results[name][i].append(data)

with open("cold_parallel_invokes.pckl", "w+b") as f:
  results = json.loads(json.dumps(results))
  pickle.dump(results, f)
