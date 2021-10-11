from wsk_interact import *
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor

host="https://172.29.200.161"

set_properties(host=host, auth="dacf4133-3c3a-42d5-956c-37200c35f427:eextGdxo1jX99Uh4ms6gnS760ExMJEG3jakg0DWJ1ldqJlukrQILpbSxEA92z3Kw")

pool = ThreadPoolExecutor(max_workers=10000)

def run_cold(zip_file, action_name, container, memory):
  path = os.path.join("../py", zip_file)
  url = add_web_action(action_name, path, container, memory=memory, host=host)
  tot = 0
  i = 0
  while i < 10:
    future = invoke_web_action_async(url, pool)
    was_cold, latency, ret_json = future.result()
    if was_cold:
      tot += latency
      i += 1
    future = None
    latency = 0
    ret_json = ""
    url = add_web_action(action_name, path, container, memory=memory, host=host)
  avg_cold = tot / i
  print("{} avg cold: {}".format(action_name, avg_cold))


def run_warm(zip_file, action_name, container, memory):
  path = os.path.join("../py", zip_file)
  url = add_web_action(action_name, path, container, memory=memory, host=host)
  tot = 0
  i = 0
  future = invoke_web_action_async(url, pool)
  was_cold, latency, ret_json = future.result()
  while i < 10:
    if not was_cold:
      tot += latency
      i += 1
    future = None
    latency = 0
    ret_json = ""
    future = invoke_web_action_async(url, pool)
    was_cold, latency, ret_json = future.result()

  avg_warm = tot / i
  print("{} avg warm: {}".format(action_name, avg_warm))


for zip_file, action_name, container, memory in zip(zips, actions, containers, mem):
  run_cold(zip_file, action_name, container, memory)
  run_warm(zip_file, action_name, container, memory)
