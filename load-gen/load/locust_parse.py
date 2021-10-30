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

df["cold"] = colds
df["latencies"] = lats

df.to_csv("{}/parsed_successes.csv".format(dir),  index=False, index_label=False)
