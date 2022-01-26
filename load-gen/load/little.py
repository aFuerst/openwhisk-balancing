import wsk_interact
import os, pickle
from time import time, sleep
from collections import defaultdict
import random
random.seed(0)

# https://corporatefinanceinstitute.com/resources/knowledge/other/littles-law/
num_servers = 3
cpus_per_server = 4
items_in_sys = num_servers * cpus_per_server
trace_len_sec = 60*10

def _loadWarmTimes():
  warm_results = None
  with open("../load/warmdata_16.pckl", "r+b") as f:
    warm_results = pickle.load(f)
  return warm_results
  min_warm_times = {}
  for k in warm_results.keys():
    min_warm_times[k] = min(warm_results[k])

def _toWeightedData(action_dict):
  sorted_cold_times = sorted(wsk_interact.cold_times, reverse=True)
  actions = sorted(action_dict.values(), key=lambda x: x.name)
  freqs = [action.freq_class for action in actions]
  # acts = list(action_dict.values())
  return actions, freqs


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

def PlotTrace(trace, pth=""):
  import pandas as pd
  import matplotlib as mpl
  import matplotlib.patches as mpatches
  mpl.rcParams.update({'font.size': 14})
  mpl.rcParams['pdf.fonttype'] = 42
  mpl.rcParams['ps.fonttype'] = 42
  mpl.use('Agg')
  import matplotlib.pyplot as plt

  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  df = pd.DataFrame.from_records(trace, columns=["time","function"])
  df["time"] = pd.to_datetime(df["time"], unit='s')
  df['time'] = df['time'].dt.second + 60* df['time'].dt.minute
  
  groups = df.groupby(by=["time"])
  xs = [time for time, group in groups]
  ys = [len(group) for time, group in groups]
  ax.plot(xs, ys)
  ax.set_ylabel("Invocations")
  ax.set_xlabel("Time (sec)")

  plt.savefig(os.path.join(pth, "trace.png"), bbox_inches="tight")
  plt.savefig(os.path.join(pth, "trace.pdf"), bbox_inches="tight")
  plt.close(fig)

def SharkToothTrace(action_dict, num_servers, numcpus, len_mins, scale: float = 1.0, peak:float=0.9):
  """
  peak - the % through the trace that represents the maximum items_per_sec
  """
  cpus_per_server = numcpus
  items_in_sys = num_servers * cpus_per_server * scale
  trace_len_sec = 60*len_mins
  # trace_len_ms = trace_len_sec * 60
  warm_times = _loadWarmTimes()

  flat = []
  for times in warm_times.values():
    flat += times
  avg_queuetime = sum(flat) / len(flat)
  items_per_sec = items_in_sys / avg_queuetime
  max_item_IAT = 1 / items_per_sec

  smoothing = 100

  curr_iat = max_item_IAT * 10
  iat_incr_amt = (curr_iat - max_item_IAT) / smoothing

  iat_increments = 1
  iat_peak_t = trace_len_sec * peak
  iat_incr_freq = iat_peak_t / smoothing  # increase iat _smoothing_ times before peak
  next_iat_incr = iat_incr_freq

  print("avg_queue_time:", avg_queuetime, "scale:", scale,
        "items_per_sec:", items_per_sec, "item_IAT:", max_item_IAT,
        "iat_incr_freq:", iat_incr_freq)

  acts, freqs = _toWeightedData(action_dict)
  # print("actions:", [act.name for act in acts])
  # print("weights:", freqs)
  t = 0
  trace = []
  while t < trace_len_sec:
    chosen = random.choices(population=acts, weights=freqs, k=1)[0]
    trace.append((t, chosen))
    t += curr_iat
    if t >= next_iat_incr:
      next_iat_incr += iat_incr_freq
      iat_increments += 1
      if iat_increments < smoothing:
        curr_iat = max(curr_iat - iat_incr_amt, max_item_IAT)
      # print(t, curr_iat, next_iat_incr)
      if iat_increments >= smoothing+3:
        # print("incrementing")
        curr_iat *= 1.5

  freqs_d = defaultdict(int)
  for t, chosen in trace:
    freqs_d[chosen.name] += 1
  # print("freqs_d", freqs_d)
  return trace

def WarmLoadTrace(action_dict, num_servers, numcpus, len_mins, scale : float =1.0):
  cpus_per_server = numcpus
  items_in_sys = num_servers * cpus_per_server * scale
  trace_len_sec = 60*len_mins
  warm_times = _loadWarmTimes()

  flat = []
  for times in warm_times.values():
    flat += times
  avg_queuetime = sum(flat) / len(flat)
  items_per_sec = items_in_sys / avg_queuetime
  item_IAT = 1 / items_per_sec
  print("avg_queue_time:", avg_queuetime, "scale:", scale, "items_per_sec:", items_per_sec, "item_IAT:", item_IAT)

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
  print("freqs_d", freqs_d)
  return trace
