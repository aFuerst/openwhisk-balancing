import os
import numpy as np
import matplotlib as mpl
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt
import pickle

colors = ['black', 'silver', 'maroon', 'orange', 'darkgreen', 'lime', 'navy', 'magenta', 'indigo', 'crimson', 'steelblue', 'pink']

results = None
with open("../load/parallel_invokes.pckl", "r+b") as f:
  results = pickle.load(f)

warm_results = None
with open("../load/warmdata_16.pckl", "r+b") as f:
  warm_results = pickle.load(f)

pts = []
labels = []
for k in warm_results.keys():
  labels.append(k)
  data = np.array(warm_results[k])
  normalizer = np.min(data)
  pts.append(data / normalizer)

fig, ax = plt.subplots()
plt.tight_layout()
fig.set_size_inches(5,3)

for i, func in enumerate(sorted(results.keys())):
  xs = []
  ys = []
  for parallelism in results[func].keys():
    xs.append(parallelism)
    mean = 0.0
    cnt = 0
    for point in results[func][parallelism]:
      was_cold, e2e_latency, response_json, activation_id = point 
      if not was_cold:
        mean += e2e_latency
        cnt += 1
    mean /= cnt # len(results[func][parallelism])

    mean /= np.min(np.array(warm_results[func]))

    ys.append(mean)
  
  ax.plot(xs,ys, label=func, color=colors[i])

ax.legend()
ax.set_xlabel("Number of parallel invocations")
ax.set_ylabel("Latency")
save_fname = os.path.join("function_parallelism.png")
plt.savefig(save_fname, bbox_inches="tight")
plt.close(fig)

