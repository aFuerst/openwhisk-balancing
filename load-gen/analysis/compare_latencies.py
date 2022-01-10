import os, sys
from collections import defaultdict
import argparse
import pandas as pd
import matplotlib as mpl
import matplotlib.patches as mpatches
mpl.rcParams.update({'font.size': 14})
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42
mpl.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser(description='')
parser.add_argument("--path", nargs='+', required=True)
parser.add_argument("--users", type=int, default=100, required=False)
args = parser.parse_args()

# users = args.users

out=[]
warm_times = [0.3525, 3.035, 1.344, 0.2484, 0.8558, 0.3944, 6.7276, 0.2661, 9.1485, 0.7716, 6.1336, 0.4874]
min_warm_times = [0.05505, 1.6623, 0.24349, 0.044388, 0.33531, 0.03527, 6.44305, 0.03420, 8.06751, 0.60664, 6.06870, 0.10007]
actions = ["cham", "cnn", "dd", "float", "gzip", "hello", "image", "lin_pack", "train", "aes", "video", "json"]
tmp = None
for i in range(len(args.path)):
  path = os.path.join(args.path[0], "parsed_successes.csv")
  if os.path.exists(path):
    tmp = pd.read_csv(path)
    break
if tmp is None:
  exit(0)
func_names = tmp["function"].unique()
for warm_time, k in zip(min_warm_times, actions):
  for name in func_names:
    if k in name:
      out.append((name,warm_time))
warm_times = pd.DataFrame(out,columns=['function',"warm"])
warm_times.index = warm_times['function']
# print(warm_times)
# print(float(warm_times[warm_times['function'] == 'aes_1']['warm']))

def path_to_key(pth):
  # print(pth)
  parts = pth.split("/")
  # print(parts, [l for l in parts if "compare" in l])
  wanted = [l for l in parts if "compare" in l]
  if len(wanted) != 1:
    print("weird file path, please support!: {}".format(pth))
    raise Exception("Failure")
  return wanted[0][len("compare-"):]

def plot(paths, users, warm):
  mean_sums = defaultdict(int)
  df_dict = defaultdict(list)
  for pth in paths:
    file = os.path.join(pth, "parsed_successes.csv")
    if not os.path.exists(file):
      continue
    if not str(users) + "-RandomForwardLoadBalancer" in pth:
      continue
    df = pd.read_csv(file)
    if warm:
      df = df[df["cold"] == False]

    grouped = df.groupby(by="function")
    for name, group in sorted(grouped, key=lambda p: float(p[0].split("_")[-1])):
      mean_sums[name] += group["latency"].mean()
    df_dict[path_to_key(pth)].append(df)

  for name in mean_sums.keys():
    mean_sums[name] = mean_sums[name] / len(paths)

  tputs = []
  colds = []
  pts = []
  labels = []
  for key in sorted(df_dict.keys()):
    box_pts = []
    dfs = df_dict[key]
    tput = 0
    cold = 0

    data = defaultdict(float)
    for df in dfs:
      tput += len(df)
      cold += len(df[df["cold"] == True])

      grouped = df.groupby(by="function")
      for name, group in grouped:
        data[name] += group["latency"].mean()

    for name in data.keys():
      data[name] /= (len(dfs) * float(warm_times[warm_times['function'] == name]['warm']))
    # print(sorted(data.items(), key=lambda x: x[0]))
    # return
    pts.append(list(data.values()))
    # pts.append(box_pts)
    labels.append(key)
    tputs.append(tput / len(dfs))
    colds.append(cold / len(dfs))

  fig, ax = plt.subplots()
  ax2 = ax.twinx()
  plt.tight_layout()
  fig.set_size_inches(5, 3)

  # new_labs = []
  # for label in labels:
  #   parts = label.split("/")
  #   wanted = [l for l in parts if "compare" in l][0]
  #   new_labs.append(wanted[len("compare-"):])

  poss = [2*i for i in range(len(pts))]
  print(len(pts), len(labels), len(poss))
  ax.boxplot(pts, labels=labels, positions=poss, showfliers=False)
  # ax.set_yscale('log')
  handles = []
  leg_labels=[]
  ax2.plot(poss, tputs, 'o', color="tab:red")
  handles.append(mpatches.Patch(color="tab:red", label='All Invokes'))

  leg_labels.append("All Invokes")
  if not warm:
    ax2.plot(poss, colds, 'o', color="tab:blue")
    handles.append(mpatches.Patch(color="tab:blue", label='Cold starts'))
    leg_labels.append("Cold starts")

  plt.xticks(rotation=90)
  ax.set_ylabel("Normalized latency")
  ax2.set_ylabel("Served functions")

  if warm:
    save_fname = os.path.join("{}-compare-overload-warm.pdf".format(args.users))
  else:
    save_fname = os.path.join("{}-compare-overload.pdf".format(args.users))

  ax.legend(handles=handles, labels=leg_labels)
  print(save_fname)

  plt.savefig(save_fname, bbox_inches="tight")
  plt.close(fig)


plot(args.path, args.users, warm=False)
plot(args.path, args.users, warm=True)
