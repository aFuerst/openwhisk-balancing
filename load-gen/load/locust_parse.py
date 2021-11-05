import sys
import os.path as path
import pandas as pd

def str2bool(v):
  return v.lower().strip() == "true"

file_path = sys.argv[1]
dir = path.dirname(file_path)
df = pd.read_csv(file_path)

print(len(df))
df = df[df["success"]]
print(len(df))
splits = df["failure_message"].apply(str.split, args=(":")).to_list()
colds = [str2bool(item[0]) for item in splits]
lats  = [float(item[1]) for item in splits]
activation_ids = [item[2].strip() for item in splits]

func_time_split = df["transaction_name"].apply(str.split, args=("-")).to_list()
times  = [float(item[1]) for item in func_time_split]
functions = [str(item[0]) for item in func_time_split]

df["cold"] = colds
df["latency"] = lats
df["function"] = functions
df["invoke_time"] = times
df["activation_id"] = activation_ids

df.to_csv("{}/parsed_successes.csv".format(dir),  index=False, index_label=False)
