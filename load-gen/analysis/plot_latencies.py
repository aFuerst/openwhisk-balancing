from collections import defaultdict
import os, sys
from datetime import datetime, timedelta
import pandas as pd
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

path = "/home/alfuerst/repos/openwhisk-balancing/load-gen/load/testlocust/sharding-100-users/"
if len(sys.argv) > 1:
  path = sys.argv[1]

users = 100
if len(sys.argv) > 2:
  users = int(sys.argv[2])

file = os.path.join(path, "parsed_successes.csv")
df = pd.read_csv(file)


##################################################################################
# Warm latencies
##################################################################################

fig, ax = plt.subplots()
# plt.tight_layout()
fig.set_size_inches(10,3)

grouped = df.groupby(by="function")
lats = []
names = []
for name, group in sorted(grouped, key=lambda p: int(p[0].split("_")[-1])):
  group = group[group["cold"] == False]
  names.append(name)
  lats.append(group["latency"])

poss = [2*i for i in range(len(lats))]
ax.boxplot(lats, labels=names, positions=poss)

ax.set_ylabel("Warm Latency (seconds)")
plt.xticks(rotation = 90)
# ax.set_xlabel("Normalized latency")
# ax.legend()
save_fname = os.path.join(path, "latencies", "{}.pdf".format("warm_latencies_box"))
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)

##################################################################################
# Cold latencies
##################################################################################

fig, ax = plt.subplots()
# plt.tight_layout()
fig.set_size_inches(10,3)
lats = []
names = []
grouped = df.groupby(by="function")
for name, group in sorted(grouped, key=lambda p: int(p[0].split("_")[-1])):
  group = group[group["cold"] == True]
  names.append(name)
  lats.append(group["latency"])

poss = [2*i for i in range(len(lats))]
ax.boxplot(lats, labels=names, positions=poss)

ax.set_ylabel("Cold Latency (seconds)")
plt.xticks(rotation = 90)
# ax.set_xlabel("Normalized latency")
# ax.legend()
save_fname = os.path.join(path, "latencies", "{}.pdf".format("cold_latencies_box"))
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)

##################################################################################
# All latencies
##################################################################################

fig, ax = plt.subplots()
# plt.tight_layout()
fig.set_size_inches(10,3)
lats = []
names = []
grouped = df.groupby(by="function")
for name, group in sorted(grouped, key=lambda p: int(p[0].split("_")[-1])):
  names.append(name)
  lats.append(group["latency"])

poss = [2*i for i in range(len(lats))]
ax.boxplot(lats, labels=names, positions=poss)

ax.set_ylabel("Latency (seconds)")
plt.xticks(rotation = 90)
# ax.set_xlabel("Normalized latency")
# ax.legend()
save_fname = os.path.join(path, "latencies", "{}.pdf".format("latencies_box"))
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)