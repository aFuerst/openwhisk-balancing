import os, sys
from collections import defaultdict
import argparse
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

users = args.users

mean_sums = defaultdict(int)
dfs = {}
for pth in args.path:
  file = os.path.join(pth, "parsed_successes.csv")
  df = pd.read_csv(file)

  grouped = df.groupby(by="function")
  for name, group in sorted(grouped, key=lambda p: int(p[0].split("_")[-1])):
    mean_sums[name] += group["latency"].mean()
  dfs[pth] = df

for name in mean_sums.keys():
  mean_sums[name] = mean_sums[name] / len(args.path)

tputs = []
pts = []
labels = []
for pth in args.path:
  box_pts = []
  df = dfs[pth]
  tputs.append(len(df))
  grouped = df.groupby(by="function")
  for name, group in grouped:
    box_pts.append(group["latency"].mean() / mean_sums[name])
  pts.append(box_pts)
  labels.append(pth)

fig, ax = plt.subplots()
ax2 = ax.twinx()
plt.tight_layout()
fig.set_size_inches(5,3)

new_labs = []
for label in labels:
  parts = label.split("/")
  wanted = [l for l in parts if "compare" in l][0]
  new_labs.append(wanted[len("compare"):])

poss = [2*i for i in range(len(pts))]
ax.boxplot(pts, labels=new_labs, positions=poss)
ax2.plot(poss, tputs, 'o', color="tab:blue")

plt.xticks(rotation = 90)
ax.set_ylabel("Normalized latency")
ax2.set_ylabel("Served functions")

save_fname = os.path.join("{}-compare-overload.png".format(args.users))
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)