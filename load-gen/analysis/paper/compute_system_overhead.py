import os, sys
from pathlib import Path
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
  return data["latency"] - running_t

def compute_ratio(data):
  running_t = compute_exe_time(data)
  over = compute_overhead(data)
  return running_t / over

def orig_name(data):
  *func, freq = data['function'].split("_")
  return "_".join(func)

def calc_pickle(path):
  import pickle
  with open(path, "r+b") as f:
    data = pickle.load(f)
  print(data.keys())
  for key in data.keys():
    print(data[key])

def calc(paths, users):
  """
  Compute time spent in function computation, the system overhead, and the running/overhead ratio 
  """
  overhead_dict = defaultdict(lambda: defaultdict(list))
  execs_dict = defaultdict(lambda: defaultdict(list))
  ratios_dict = defaultdict(lambda: defaultdict(list))

  mean_dict = defaultdict(list)
  min_dict = defaultdict(list)
  max_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if not str(users) + "-" in pth:
      continue
    df = pd.read_csv(file)

    # only warms
    df = df[df["cold"] == False]

    df["overhead"] = df.apply(compute_overhead, axis=1)
    # overheads = overheads[overheads>0]
    df["exec"] = df.apply(compute_exe_time, axis=1)
    # execs = execs[execs >0]
    df["ratio"] = df.apply(compute_ratio, axis=1)
    # ratio = ratio[ratio>0]
    df["func"] = df.apply(orig_name, axis=1)
    df = df[df["overhead"] > 0]

    for name, group in df.groupby(by=["func"]):
      # print(name, group["overhead"].min(), group["overhead"].mean(), group["overhead"].quantile(0.99))

      min_dict[name].append(group["overhead"].min())
      mean_dict[name].append(group["overhead"].mean())
      max_dict[name].append(group["overhead"].quantile(0.99))

  # fixup because bad placement of internal func timing
  # can remove on future runs
  for func in sorted(mean_dict.keys()):
    min = np.median(min_dict[func])
    mean = np.median(mean_dict[func])
    max = np.median(max_dict[func])
    
    if func in ["train", "video"]:
      orig_min = min
      min = np.median(min_dict["cnn"])
      mean = mean - (orig_min - min)
      max = max - (orig_min - min)

    print(func, min, mean, max)
    # print(bl, np.median(execs_dict[bl]), np.quantile(execs_dict[bl], [0.1, 0.5, 0.8, 0.90, 0.99]))
    # print(bl, np.median(ratios_dict[bl]), np.quantile(ratios_dict[bl], [0.1, 0.5, 0.8, 0.90, 0.99]))


if ".pckl" in args.path[0]:
  calc_pickle(args.path[0])
  exit()

calc(args.path, args.users)
