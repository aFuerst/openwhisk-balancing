from wsk_interact import *
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
# import pandas as pd
from random import randint

host="https://172.29.200.161"
auth="bae2d81d-835b-42b2-9659-8e82fa8e18c8:CymDv9WEzMVgVs4m07QlR1HSS0XOGHZNKw5Kia44Hl43RVsUk424xrD890PUea1L"

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
  path = os.path.join("../py", zip_file)
  for freq in [2, 20, 50]:
    name = action_name + "_" + str(freq)
    url = add_web_action(name, path, container, memory=memory, host=host)
    action_dict[name] = Action(name, url, warm_time, cold_time, freq)

trace_time_sec = 60 * 10
eleven_mins_sec = 60 * 11
trace = []

class Invocation:
  def __init__(self, name, time, url):
    self.name = name
    self.time = time
    self.url = url

for i, (name, action) in enumerate(action_dict.items()):
  invok_time = i
  invocations = []

  # max is just outside OW keepalive
  sep = min(action.coldtime * action.freq_class,  eleven_mins_sec)
  while invok_time < trace_time_sec:
    invocations.append(Invocation(name, invok_time, action.url))
    invok_time += sep
  print("to invoke:", name, len(invocations))
  trace += invocations

trace = sorted(trace, key=lambda x: x.time)
futures = []

print("trace len", len(trace))


start = time()
for invocation in trace:
  t = time()
  while t - start < invocation.time:
    t = time()

  future = invoke_web_action_async(invocation.url, pool, auth=auth, host=host)
  futures.append((invocation, future))

print("\n\n done invoking \n\n")

ready = all([future.done() for _, future in futures])
while not ready:
  ready = all([future.done() for _, future in futures])
  sleep(1)

print("\n\n ALL READY \n\n")

cold_results = defaultdict(int)
warm_results = defaultdict(int)

data = []
for invocation, future in futures:
  was_cold, latency, ret_json = future.result()
  data.append( (invocation.name, was_cold, latency) )
  print(invocation.name, was_cold, latency)
  if was_cold is None:
    pass
  if was_cold:
    cold_results[invocation.name] += 1
  else:
    warm_results[invocation.name] += 1

print("warm results, total=", sum(warm_results.values()), warm_results)
print("cold results, total=", sum(cold_results.values()), cold_results)

# df = pd.DataFrame.from_records(data, columns=["invokname", "was_cold", "latency"])
# df.to_csv("run.csv")


