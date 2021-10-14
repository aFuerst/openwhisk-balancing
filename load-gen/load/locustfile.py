from locust import HttpUser, task, constant, events, between, TaskSet
import little
from wsk_interact import *
import random
import os

host = os.environ["HOST"]
auth = os.environ["AUTH"]
# requests_per_sec = float(os.environ["RPS"])
# num_users = int(os.environ["LOCUST_USERS"])
# rps = float(os.environ["LOCUST_RPS"])
# global_wait_time = num_users / requests_per_sec
# print("per-user wait time, seconds:", global_wait_time)

class Action:
  def __init__(self, name, url, warmtime, coldtime, freq_class):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime
    self.freq_class = freq_class

set_properties(host=host, auth=auth)
action_dict = {}

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  path = os.path.join("../ow-actions", zip_file)
  for freq in [40, 75, 100, 150]:
    name = action_name + "_" + str(freq)
    url = add_web_action(name, path, container, memory=memory, host=host)
    action_dict[name] = Action(name, url, warm_time, cold_time, freq)

acts, freqs = little._toWeightedData(action_dict)

class FirstUser(HttpUser):
  wait_time = between(0, 1)
  host = host

  @task
  def hello_world(self):
    chosen = random.choices(population=acts, weights=freqs, k=1)[0]
    self.client.get(chosen.url, verify=False)
