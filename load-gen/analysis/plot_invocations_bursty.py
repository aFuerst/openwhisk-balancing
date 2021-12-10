import os, sys, argparse
from datetime import datetime, timezone, timedelta
from numpy import dtype
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

def date_idx_to_min(idx):
  mins = (idx.second + idx.minute*60)# + idx.hour*60*60)
  # mins -= 60*60
  return mins / 60

def fixup_datetime(index):
  if index.iloc[0].hour < index.iloc[-1].hour:
    delta = timedelta(minutes=10)
    index += delta
    # print(type(index))
    # print(index.iloc[0], index.iloc[-1])
  return index
  # mins = (idx.second + idx.minute*60 + idx.hour*60*60)
  # # mins -= 60*60
  # return mins / 60

def plot(path):
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)
  save_pth = path
  file = os.path.join(path, "parsed_successes.csv")

  df = pd.read_csv(file)
  df["start_time"] = pd.to_datetime(df["start_time"])
  df = df.sort_values("start_time")


  print(df["start_time"].iloc[0], df["start_time"].iloc[-1])
  df["start_time"] = fixup_datetime(df["start_time"])

  df["start_time"] = df["start_time"].dt.round("10s")


  nonbursty = df[(df["function"] != "gzip_40") & (df["function"] != "aes_40")]
  groups = nonbursty.groupby("start_time")
  # groups = df.groupby("start_time")
  ax.plot([date_idx_to_min(time) for time, grp in groups], [len(grp) for time, grp in groups], color='k', label="All")

  aes = df[df["function"] == "aes_40"]
  groups = aes.groupby("start_time")
  ax.plot([date_idx_to_min(time) for time, grp in groups], [len(grp) for time, grp in groups], color='tab:blue', label="aes")

  aes = df[df["function"] == "gzip_40"]
  groups = aes.groupby("start_time")
  ax.plot([date_idx_to_min(time) for time, grp in groups], [len(grp) for time, grp in groups], color='tab:green', label="gzip")


  bursty = df[(df["function"] == "gzip_40") | (df["function"] == "aes_40")]
  groups = bursty.groupby("start_time")
  ax.plot([date_idx_to_min(time) for time, grp in groups], [len(grp)
          for time, grp in groups], color='tab:brown', label="Bursty")

  # for f in sorted(df["function"].unique()):
  #   print(f, len(df[df["function"] == f]))

  ax.set_ylabel("Invocations")
  ax.set_xlabel("Time (min)")
  ax.legend()
  # ax.set_xticklabels(ax.get_xticks(), rotation=45, rotation_mode="anchor")

  save_fname = os.path.join(save_pth, "{}-invocations-bursty.png".format(users))
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

plot(path)
