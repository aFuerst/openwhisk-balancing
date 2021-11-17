from collections import defaultdict
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])


file = "controller0_logs.log"
file = os.path.join(path, file)

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
        elapsed[aid] = parsedtime-tracked[aid]
        del tracked[aid]
        # break

print(sum([x.total_seconds() for x in elapsed.values()]) / len(elapsed))
