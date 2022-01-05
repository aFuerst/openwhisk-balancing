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

invoker_cnts = defaultdict(int)

for pth in path:
  file = os.path.join(pth, "controller0_logs.log")
  if not os.path.exists(file):
    continue
  if not str(users) + "-" in pth:
    continue
  transactions = os.path.join(pth, "parsed_successes.csv")
  df = pd.read_csv(transactions)

  with open(file) as f:
    for line in f:
      if "posting topic" in line and "tid_sid_invokerHealth" not in line:
        # [2022-01-05T00:51:53.272Z] [INFO] [#tid_0itKmVWdXUmEpB30layYUHU3BH6BPtZ4] [RoundRobinLB] posting topic 'invoker4' with activation id '0bb430b725d143f3b430b725d183f3d8' [marker:controller_kafka_start:2]
        marker = "posting topic "
        pos = line.find(marker)
        dist_start = pos + len(marker)  # line[pos:len(marker)]
        dist_end = line.find(" ", dist_start)
        invoker = line[dist_start:dist_end]

        marker = "activation id "
        pos = line.find(marker)
        dist_start = pos + len(marker)  # line[pos:len(marker)]
        dist_end = line.find(" ", dist_start)
        act = line[dist_start:dist_end]
        act = act.strip("'")
        invoker_cnts[invoker] += 1
        if act in df["activation_id"]:
          invoker_cnts[invoker] += 1


print(invoker_cnts)
