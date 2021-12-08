from wsk_interact import *
import os
from time import time, sleep
from collections import defaultdict
# import pandas as pd

host="https://172.29.200.161:10001"
auth="a0ebde37-0272-4d2e-b2ed-77f93f9e0158:WW5BI37G7ppqVPnOAgapbsUxGirIsBo1iXATp7ufGdK5wO44CbPbQvtUbCdHxU50"

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
  while len(warm_results[name]) < 10:
    start = time()
    r = requests.get(action.url, verify=False)
    latency = time() - start
    ret_json = r.json()
    if "cold" in ret_json:
        if not ret_json["cold"]:
          warm_results[name].append(latency)
        else:
          warm_results[name].append(latency)

for k in warm_results.keys():
  print("{} warm results, avg = {}; min = {}".format(k, sum(warm_results[k]) / len(warm_results[k]), min(warm_results[k])))
  # if len(cold_results[k]) > 0:
  #   print("cold results, avg = {}; min = {}".format(k), sum(cold_results[k]) / len(cold_results[k]), min(cold_results[k]))

# df = pd.DataFrame.from_records(data, columns=[func, "was_cold", "latency"])
# df.to_csv("run.csv")


