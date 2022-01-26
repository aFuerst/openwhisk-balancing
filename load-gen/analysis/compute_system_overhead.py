import os, sys
from collections import defaultdict
import argparse
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

def path_to_key(pth):
  # print(pth)
  parts = pth.strip("/").split("/")
  try:
    return parts[-1].split("-")[1]
  except:
    return "test"

def compute_exe_time(data):
  running_t = data["end_t"] - data["start_t"]
  return running_t

def compute_overhead(data):
  running_t = compute_exe_time(data)
  # if (data["latency"] - running_t) < 0:
  #   print(data['function'], data["latency"], data["end_t"] -
  #         data["start_t"], data["duration"]/1000)
  return data["latency"] - running_t

def compute_ratio(data):
  running_t = compute_exe_time(data)
  over = compute_overhead(data)
  return running_t / over

def calc(paths, users):
  """
  Compute time spent in function computation, the system overhead, and the running/overhead ratio 
  """
  overhead_dict = defaultdict(list)
  execs_dict = defaultdict(list)
  ratios_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if not str(users) + "-" in pth:
      continue
    df = pd.read_csv(file)

    # only warms
    df = df[df["cold"] == False]

    overheads = df.apply(compute_overhead, axis=1)
    overheads = overheads[overheads>0]
    execs = df.apply(compute_exe_time, axis=1)
    execs = execs[execs >0]
    ratio = df.apply(compute_ratio, axis=1)
    ratio = ratio[ratio>0]

    overhead_dict[path_to_key(pth)] += overheads.to_list()
    execs_dict[path_to_key(pth)] += execs.to_list()
    ratios_dict[path_to_key(pth)] += ratio.to_list()

  for bl in sorted(overhead_dict.keys()):
    print(bl, np.median(overhead_dict[bl]), np.quantile(overhead_dict[bl], [0.1, 0.5, 0.8, 0.90, 0.99]))
    print(bl, np.median(execs_dict[bl]), np.quantile(execs_dict[bl], [0.1, 0.5, 0.8, 0.90, 0.99]))
    print(bl, np.median(ratios_dict[bl]), np.quantile(ratios_dict[bl], [0.1, 0.5, 0.8, 0.90, 0.99]))



calc(args.path, args.users)
