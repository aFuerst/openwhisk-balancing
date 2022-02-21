from collections import defaultdict
from datetime import datetime, timedelta
import os, argparse
import numpy as np
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import pickle

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", type=str, required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

def fixup_datetime(index):
  if index.iloc[0].hour < index.iloc[-1].hour:
    diff = index.iloc[0] - index.iloc[-1]
    delta = timedelta(seconds=diff.seconds)
    index += delta
    # print(index.iloc[0], index.iloc[-1])
  return index

def date_idx_to_min(idx):
  mins = (idx.second + idx.minute*60)# + idx.hour*60*60)
  # mins -= 60*60
  return mins / 60

warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

min_warm_times = {}
for k in warm_results.keys():
  min_warm_times[k] = min(warm_results[k])

path = os.path.join(args.path, "parsed_successes.csv")
tmp = pd.read_csv(path)
out = []
func_names = tmp["function"].unique()
for k, warm_time in min_warm_times.items():
  for name in func_names:
    if k in name:
      out.append((name,warm_time))
warm_times = pd.DataFrame(out,columns=['function',"warm"])
warm_times.index = warm_times['function']

def get_normed_lat(data):
  return float(data["latency"] / warm_times[warm_times["function"] == data["function"]]["warm"])

df = pd.read_csv(path, header=0, usecols=["function", "cold", "latency", "activation_id", "start_time"])
df = df[df["cold"]==False]
df["start_time"] = fixup_datetime(pd.to_datetime(df["start_time"]))
df["normed_lat"] = df.apply(get_normed_lat, axis=1)
df["start_time"] = df["start_time"].dt.round("10s")
df = df[df["normed_lat"] < 100]

groups = df.groupby(["start_time"])
# print(len(groups))
# print(df["normed_lat"].describe())

xs = []
ys = []
for time, group in sorted(groups, key= lambda x: x[0]):
  xs.append(date_idx_to_min(time))
  ys.append(group["normed_lat"].mean())

fig, ax = plt.subplots()
plt.tight_layout()

ax.plot(xs, ys, color='navy')#, label="Load")

invok_start_times = {'invoker0/0': datetime(2022, 1, 25, 19, 4, 47, 439000), 'invoker1/1': datetime(2022, 1, 25, 19, 6, 45, 277000), 'invoker2/2': datetime(2022, 1, 25, 19, 8, 28, 943000), 'invoker3/3': datetime(2022, 1, 25, 19, 9, 53, 48000), 'invoker4/4': datetime(2022, 1, 25, 19, 10, 57, 718000)}

xs = []
for key, date in invok_start_times.items():
  xs.append(date_idx_to_min(date))
ax.vlines(xs, 0, max(ys), color='red', label="Invoker Start", linestyles='dashed')

# b, a = np.polyfit(xs, ys, deg=1)
# xseq = np.linspace(min(xs), max(xs), num=100)
# ax.plot(xseq, a + b * xseq, color='red', label="Polyfit")

ax.set_ylabel("Normalized Latency")
ax.set_xlabel("Time (min)")
ax.legend()

fig.set_size_inches(5,3)
save_fname = os.path.join(args.path, "scaling_lat_over_time.pdf")

plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)
