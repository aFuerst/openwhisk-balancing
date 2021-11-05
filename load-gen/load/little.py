import wsk_interact
import os
from time import time, sleep
from collections import defaultdict
import random
random.seed(0)

# https://corporatefinanceinstitute.com/resources/knowledge/other/littles-law/
num_servers = 3
cpus_per_server = 4
items_in_sys = num_servers * cpus_per_server
trace_len_sec = 60*10


def _toWeightedData(action_dict):
  sorted_cold_times = sorted(wsk_interact.cold_times, reverse=True)
  freqs = [action.freq_class for action in action_dict.values()]
  acts = list(action_dict.values())
  return acts, freqs


def ColdLoadTrace(action_dict, numcpus=4, len_mins=10):
  num_servers = 3
  cpus_per_server = numcpus
  items_in_sys = num_servers * cpus_per_server
  trace_len_sec = 60*len_mins

  avg_queuetime = sum(wsk_interact.cold_times) / len(wsk_interact.cold_times)
  items_per_sec = items_in_sys / avg_queuetime
  item_IAT = 1 / items_per_sec
  print("items_per_sec:", items_per_sec, "item_IAT:", item_IAT)
  acts, freqs = _toWeightedData(action_dict)
  print("actions:", [act.name for act in acts])
  print("weights:", freqs)
  chosen = random.choices(population=acts, weights=freqs, k=1)[0]
  # print(chosen.name)
  t = 0
  trace = []
  while t < trace_len_sec:
    chosen = random.choices(population=acts, weights=freqs, k=1)[0]
    trace.append((t, chosen))
    t += item_IAT

  # print(len(trace))
  # print(trace[-1][0], trace[-1][1].name)
  freqs_d = defaultdict(int)
  for t, chosen in trace:
    freqs_d[chosen.name] += 1
  print("freqs_d",freqs_d)
  return trace


def WarmLoadTrace(action_dict):
  avg_queuetime = sum(wsk_interact.warm_times) / len(wsk_interact.warm_times)
  items_per_sec = items_in_sys / avg_queuetime
  item_IAT = 1 / items_per_sec
  print("items_per_sec:", items_per_sec, "item_IAT:", item_IAT)
  acts, freqs = _toWeightedData(action_dict)
  chosen = random.choices(population=acts, weights=freqs, k=1)[0]
  # print(chosen.name)
  t = 0
  trace = []
  while t < trace_len_sec:
    chosen = random.choices(population=acts, weights=freqs, k=1)[0]
    trace.append((t, chosen))
    t += item_IAT

  # print(len(trace))
  # print(trace[-1][0], trace[-1][1].name)
  freqs_d = defaultdict(int)
  for t, chosen in trace:
    freqs_d[chosen.name] += 1
  print("freqs_d",freqs_d)
  return trace
