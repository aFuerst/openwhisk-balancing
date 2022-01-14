import sys
import os.path as path
import pandas as pd
import json

def str2bool(v):
  return v.lower().strip() == "true"

file_path = sys.argv[1]
dir = path.dirname(file_path)
df = pd.read_csv(file_path)

# print(len(df))
df = df[df["success"]]
splits = df["failure_message"].apply(str.split, args=(":")).to_list()
colds = [str2bool(item[0]) for item in splits]
lats  = [float(item[1]) for item in splits]
activation_ids = [item[2].strip() for item in splits]
# print(len(splits[0]))
if len(splits[0]) > 3:
  if len(splits[0]) > 5:
    # json dump
    def recover_json(data):
      recombined = ":".join(splits[0][3:])
      return json.loads(recombined)
    # print(splits[0][3:])
    # recombined = ":".join(splits[0][3:])
    # print(recombined)
    # print(json.loads(recombined))
    starts = [recover_json(item)["start"] for item in splits]
    ends = [recover_json(item)["end"] for item in splits]
    # print(starts[0], ends[0], ends[0] - starts[0])
    # exit()
  else:
    starts = [float(item[3]) for item in splits]
    ends = [float(item[4]) for item in splits]

func_time_split = df["transaction_name"].apply(str.split, args=("-")).to_list()
times  = [float(item[1]) for item in func_time_split]
functions = [str(item[0]) for item in func_time_split]

df["cold"] = colds
df["latency"] = lats
df["function"] = functions
df["invoke_time"] = times
df["activation_id"] = activation_ids
if len(splits[0]) > 3:
  df["start_t"] = starts
  df["end_t"] = ends
print(len(df), len(df[df["cold"] == True]))

df.to_csv("{}/parsed_successes.csv".format(dir),  index=False, index_label=False)
