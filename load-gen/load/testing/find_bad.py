import pandas as pd
import os, os.path

base="/extra/alfuerst/openwhisk-logs-two/30min-compare/"
backdir="/extra/alfuerst/openwhisk-logs-two/30min-compare-back/"
bad = 0
for i in range(4):
  dir = os.path.join(base, str(i))
  for subdir in os.listdir(dir):
    file_pth = os.path.join(dir, subdir, "parsed_successes.csv")
    if os.path.exists(file_pth):
      df = pd.read_csv(file_pth)
      if len(df["function"].unique()) != 132:
        dest = os.path.join(backdir, str(i), subdir)
        os.makedirs(dest, exist_ok=True)
        os.rename(os.path.join(dir, subdir), dest)
        print(i, subdir, len(df["function"].unique()))
        bad += 1
print(bad)
