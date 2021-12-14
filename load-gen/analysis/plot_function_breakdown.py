import os
import numpy as np
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import pickle


warm_results = None
with open("../load/warmdata2.pckl", "r+b") as f:
  warm_results = pickle.load(f)

pts = []
labels = []
for k in warm_results.keys():
  labels.append(k)
  data = np.array(warm_results[k])
  normalizer = np.mean(data)
  pts.append(data / normalizer)

pos = [i for i in range(len(labels))]
widths = [0.7 for i in range(len(labels))]

fig, ax = plt.subplots()
plt.tight_layout()
fig.set_size_inches(5,3)

ax.violinplot(pts, pos, widths=widths)

ax.xaxis.set_tick_params(direction='out', rotation = 45)
ax.xaxis.set_ticks_position('bottom')
ax.set_xticks(pos)#, labels)
ax.set_xticklabels(labels)
# ax.set_xlim(0.25, len(labels) + 0.75)
# ax.set_xlabel('Sample name')

save_fname = os.path.join("function_breakdown_mean.png")
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)

#################################################################

fig, ax = plt.subplots()
plt.tight_layout()
fig.set_size_inches(5,3)

pts = []
labels = []
for k in warm_results.keys():
  labels.append(k)
  data = np.array(warm_results[k])
  normalizer = min(data)
  pts.append(data / normalizer)
ax.violinplot(pts, pos, widths=widths)

ax.xaxis.set_tick_params(direction='out', rotation = 45)
ax.xaxis.set_ticks_position('bottom')
ax.set_xticks(pos)#, labels)
ax.set_xticklabels(labels)
# ax.set_xlim(0.25, len(labels) + 0.75)
# ax.set_xlabel('Sample name')

save_fname = os.path.join("function_breakdown_min.png")
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)
