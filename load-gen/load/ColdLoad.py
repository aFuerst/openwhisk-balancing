from wsk_interact import *
import little
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import pandas as pd
from random import randint
import argparse

parser = argparse.ArgumentParser(description='Run FaasCache Simulation')
parser.add_argument("--savepth", type=str, default="/path/to/place/out.csv", required=True)
parser.add_argument("--host", type=str, default="https://172.29.200.161:10001", required=False)
parser.add_argument("--auth", type=str, default="3012593d-2f77-4991-8413-17fb04f74f9d:haEBFhaLcFregYZMfNcein4YxBGvg85VCF4pSgKqCGoCpHzCna0s6ZbPoXhLa0t4", required=False)
parser.add_argument("--numcpus", type=float, default=4, required=False)
parser.add_argument("--lenmins", type=int, default=10, required=False)
args = parser.parse_args()

host=args.host
auth=args.auth
set_properties(host=host, auth=auth)
pool = ThreadPoolExecutor(max_workers=10000)
class Action:
  def __init__(self, name, url, warmtime, coldtime, freq_class):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime
    self.freq_class = freq_class

action_dict = {}

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  # if action_name == "video":
  #   continue
  # if cold_time > 5:
  #   continue
  path = os.path.join("../ow-actions", zip_file)
  for freq in [40, 75, 100, 150]:
    name = action_name + "_" + str(freq)
    url = add_web_action(name, path, container, memory=memory, host=host)
    action_dict[name] = Action(name, url, warm_time, cold_time, freq)

trace = little.ColdLoadTrace(action_dict, args.numcpus, args.lenmins)
print("trace len", len(trace))

futures = []
start = time()
for invok_t, action in trace:
  t = time()
  while t - start < invok_t:
    t = time()

  future = invoke_web_action_async(action.url, pool, auth, host)
  futures.append((action, future))

print("\n\n done invoking \n\n")

ready = all([future.done() for _, future in futures])
while not ready:
  ready = all([future.done() for _, future in futures])
  sleep(1)

print("\n\n ALL READY \n\n")

cold_results = defaultdict(int)
warm_results = defaultdict(int)
none_results = defaultdict(int)

data = []
for action, future in futures:
  was_cold, latency, ret_json, activation_id = future.result()
  data.append( (action.name, was_cold, latency, activation_id) )
  print(action.name, was_cold, latency)
  if was_cold == True:
    cold_results[action.name] += 1
  elif was_cold == False:
    warm_results[action.name] += 1
  else:
    none_results[action.name] += 1

print("warm results, total=", sum(warm_results.values()), warm_results)
print("cold results, total=", sum(cold_results.values()), cold_results)
print("none results, total=", sum(none_results.values()), none_results)

df = pd.DataFrame.from_records(data, columns=["lambda", "was_cold", "latency", "activationid"])
df.to_csv(args.savepth, index=False)
