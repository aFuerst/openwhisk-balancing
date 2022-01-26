from wsk_interact import *
import little
import os, pickle, argparse
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import pandas as pd

parser = argparse.ArgumentParser(description='Run!')
parser.add_argument("--savepth", type=str, default="/path/to/place/", required=True)
parser.add_argument("--host", type=str, default="https://172.29.200.161:10001", required=False)
parser.add_argument("--auth", type=str, default="2808ef88-a07b-4c0a-b43c-35aae16b23f1:uSBzPCl92yjKFWTEOFulTWFUlXttpAIOOp50b1fsIu0xULSoHlEQzqhpgGXbetEk", required=False)
parser.add_argument("--numcpus", type=float, default=4, required=False)
parser.add_argument("--lenmins", type=int, default=10, required=False)
parser.add_argument("--numservers", type=int, default=8, required=False)
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
  for freq in class_frequencies:
    name = action_name + "_" + str(freq)
    # url = ""
    url = add_web_action(name, path, container, memory=memory, host=host)
    action_dict[name] = Action(name, url, warm_time, cold_time, freq)

trace = little.SharkToothTrace(action_dict, num_servers=args.numservers, numcpus=args.numcpus, len_mins=args.lenmins)
print("trace len", len(trace))

trace_pckl_pth = os.path.join(args.savepth, "trace.pckl")
with open(trace_pckl_pth, "w+b") as f:
  pickle.dump(trace, f)

little.PlotTrace(trace, pth=args.savepth)
futures = []
start = time()
for invok_t, action in trace:
  t = time()
  while t - start < invok_t:
    t = time()

  future = invoke_web_action_async(action.url, pool, auth, host)
  futures.append((action, future))

print("\n\n done invoking \n\n")


done_t = time()
wait_t = time()
ready = all([future.done() for _, future in futures])
while not ready:
  ready = all([future.done() for _, future in futures])
  sleep(1)
  wait_t = time()
  if wait_t - done_t > 60*5:
    # five minutes then kill
    break

print("\n\n ALL READY \n\n")

cold_results = defaultdict(int)
warm_results = defaultdict(int)
none_results = defaultdict(int)

data = []
for action, future in futures:
  if future.done():
    try:
      was_cold, latency, ret_json, activation_id, start = future.result()
    except:
      continue
    data.append((action.name, was_cold, latency,
                ret_json, activation_id, start))
    # print(action.name, was_cold, latency)
    if was_cold == True:
      cold_results[action.name] += 1
    elif was_cold == False:
      warm_results[action.name] += 1
    else:
      none_results[action.name] += 1
  else:
    # ignore cancellation success
    canceled = future.cancel()
    none_results[action.name] += 1
    # record dropped data
    data.append((action.name, None, None, None, None, None))

pckl_pth = os.path.join(args.savepth, "data.pckl")
with open(pckl_pth, "w+b") as f:
  pickle.dump(data, f)


print("warm results, total=", sum(warm_results.values()), warm_results)
print("cold results, total=", sum(cold_results.values()), cold_results)
print("none results, total=", sum(none_results.values()), none_results)

# df = pd.DataFrame.from_records(data, columns=["lambda", "was_cold", "latency", "activationid"])
# data_pth = os.path.join(args.savepth, "data.pckl")
# df.to_csv(data_pth, index=False)
