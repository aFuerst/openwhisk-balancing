from wsk_interact import *
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor

host="https://172.29.200.161"

set_properties(host=host, auth="d987295b-14d2-475a-972c-6cac90106eba:YZjI1kD9TtrnyzpisjArKXHXR9ZKvAEo6Ra48zraUXgDQarX5FCO5sI8U0RXCDIo")

pool = ThreadPoolExecutor(max_workers=10000)

action_dict = {}

for zip_file, action_name, container, memory in zip(zips, actions, containers, mem):
    path = os.path.join("../py", zip_file)
    url = add_web_action(action_name, path, container, memory=memory, host=host)
    action_dict[action_name] = url

futures = []

idx = 0
for i in range(50):
  action_name = "hello"
  # for action_name in actions:
  idx += 1
  url = action_dict[action_name]
  future = invoke_web_action_async(url, pool)
  futures.append((action_name, future))
  print("invoked {}".format(idx))
  sleep(0.5)

print("\n\n done invoking \n\n")

ready = all([future.done() for _, future in futures])
while not ready:
  ready = all([future.done() for _, future in futures])
  sleep(1)

print("\n\n ALL READY \n\n")

for action_name, future in futures:
  was_cold, latency, ret_json = future.result()
  print(action_name, was_cold, latency)