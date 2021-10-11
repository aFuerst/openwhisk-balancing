from wsk_interact import *
import little
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
# import pandas as pd
from random import randint

host="https://172.29.200.161"
auth="bae2d81d-835b-42b2-9659-8e82fa8e18c8:CymDv9WEzMVgVs4m07QlR1HSS0XOGHZNKw5Kia44Hl43RVsUk424xrD890PUea1L"

set_properties(host=host, auth=auth)
pool = ThreadPoolExecutor(max_workers=10000)
class Action:
  def __init__(self, name, url, warmtime, coldtime, freq_class):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime
    self.freq_class = freq_class

action_dict = {}

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  path = os.path.join("../py", zip_file)
  for freq in [2, 20, 50]:
    name = action_name + "_" + str(freq)
    url = add_web_action(name, path, container, memory=memory, host=host)
    action_dict[name] = Action(name, url, warm_time, cold_time, freq)

little.WarmLoadTrace(action_dict)
