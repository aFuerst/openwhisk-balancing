from collections import defaultdict
import os
import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

path = args.path
users = args.users
# print(path)

# file = "controller0_logs.log"
# file = os.path.join(path, file)


def path_to_lb(pth):
  parts = pth.split("/")
  return parts[-1].split("-")[1]


elapsed_times = defaultdict(list)
for pth in path:
  file = os.path.join(pth, "controller0_logs.log")
  if not os.path.exists(file):
    continue
  if not str(users) + "-" in pth:
    continue
  # df = pd.read_csv(file)
  # print(pth)
  tracked = {}
  elapsed = {}
  with open(file) as f:
    for line in f:
      if "action activation id:" in line:
        s = line.split(" ")
        time = s[0].strip("[]").strip()
        parsedtime = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
        for seg in s:
          if len(seg) == len("38f3b85a5b3a410db3b85a5b3a110d6e"):
            aid = seg
        tracked[aid] = parsedtime
        # print(time, aid)
        # break
      if "scheduled activation" in line:
        s = line.split(" ")
        time = s[0].strip("[]").strip()
        parsedtime = datetime.strptime(time, "%Y-%m-%dT%H:%M:%S.%fZ")
        for seg in s:
          if len(seg) == len("38f3b85a5b3a410db3b85a5b3a110d6e"):
            aid = seg
        if aid in tracked:
          # print(aid, parsedtime-tracked[aid])
          elapsed_times[path_to_lb(pth)].append(parsedtime - tracked[aid])
          del tracked[aid]
          # break

for key in elapsed_times.keys():
  print("{}: {}".format(key, sum([x.total_seconds() for x in elapsed_times[key]]) / len(elapsed_times[key])))
