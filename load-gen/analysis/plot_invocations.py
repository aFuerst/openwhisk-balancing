import os, sys, argparse
from datetime import datetime, timezone
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

def plot(path):
  fig, ax = plt.subplots()
  plt.tight_layout()
  fig.set_size_inches(5,3)
  save_pth = path
  file = os.path.join(path, "parsed_successes.csv")

  df = pd.read_csv(file)
  df["start_time"] = pd.to_datetime(df["start_time"])
  df["start_time"] = df["start_time"].dt.round("1s")
  groups = df.groupby("start_time")
  # ys= []
  # xs=[]
  # for time, grp in groups:
  #   ys.append(len(grp))
  #   xs.append(time)

  ax.plot([time for time, grp in groups], [len(grp) for time, grp in groups], color='k')

  ax.set_ylabel("Invocations")
  ax.set_xlabel("Time (sec)")
  ax.set_xticklabels(ax.get_xticks(), rotation=45, rotation_mode="anchor")

  save_fname = os.path.join(save_pth, "{}-invocations.pdf".format(users))
  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)

plot(path)
