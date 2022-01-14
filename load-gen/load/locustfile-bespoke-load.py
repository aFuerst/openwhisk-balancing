from locust import HttpUser, task, constant, events, between, TaskSet, SequentialTaskSet, LoadTestShape
from locust_plugins.transaction_manager import TransactionManager
import little
from wsk_interact import *
import random
import os
from time import time
import copy

host = os.environ["HOST"]
auth = os.environ["AUTH"]
users = int(os.environ["USER_TOT"])

class Action:
  def __init__(self, name, url, warmtime, coldtime, freq_class):
    self.name = name
    self.url = url
    self.coldtime = coldtime
    self.warmtime = warmtime
    self.freq_class = freq_class

  def __str__(self) -> str:
      return "{}, {}".format(self.name, self.freq_class)

set_properties(host=host, auth=auth)
normal_action_dict = {}

for zip_file, action_name, container, memory, warm_time, cold_time in zip(zips, actions, containers, mem, warm_times, cold_times):
  path = os.path.join("../ow-actions", zip_file)
  url = add_web_action(action_name, path, container, memory=memory, host=host)
  normal_action_dict[action_name] = Action(action_name, url, warm_time, cold_time, 1)

acts, normal_freqs = little._toWeightedData(normal_action_dict)
max_wait = 10*60

class TransactionalWaitForFunctionCoplete(SequentialTaskSet):
     
  def on_start(self):
    self.u, self.p = auth.split(":")
    self.max_wait = 10*60

    self.tm = TransactionManager()

  @task
  def invoke(self):
    # if self.user.environment.shape_class.bursty:
    #   print("bursty")
    action = random.choices(population=acts, weights=normal_freqs, k=1)[0]
    # else:
    #   print("not bursty")
    #   action = random.choices(population=acts, weights=normal_freqs, k=1)[0]
    t = time()
    invoke_name = action.name + "-" + str(t)
    self.tm.start_transaction(invoke_name)
    r = self.client.get(action.url, verify=False)
    # lat = time() - t
    # self.tm.end_transaction(success=True, transaction_name=invoke_name, failure_message=str(lat))
    # return
    success = True
    failure_msg = ""
    try:
      if "x-openwhisk-activation-id" in r.headers:
        activation_id = r.headers["x-openwhisk-activation-id"]
      else:
        activation_id="ERROR"
      if r.status_code == 502:
        success = False
        failure_msg = "BAD_GATEWAY"
      if r.status_code == 202:
        # invocation timed out, poll for result
        # https://172.29.200.161/api/v1/namespaces/_/activations/7f6564cf8c5f494da564cf8c5fd94d3f
        resp_json = r.json()
        poll_url = "{}/api/v1/namespaces/_/activations/{}".format(host, activation_id)
        i = 0
        r = requests.get(poll_url, verify=False, auth=(self.u,self.p))
        while r.status_code != 200 and i < max_wait:
          if r.status_code == 502:
            success = False
            failure_msg = "BAD_GATEWAY"
            break
          sleep(2)
          r = requests.get(poll_url, verify=False, auth=(self.u,self.p))
          i += 1
        if i == max_wait:
          success = False
          failure_msg = "Activation with ID {} failed to finish reasonbly. {}".format(activation_id)

        ret_json = r.json()
        if "response" in ret_json and "result" in ret_json["response"] and "body" in ret_json["response"]["result"]:
          ret_json = ret_json["response"]["result"]["body"]
      else:
        ret_json = r.json()
      if "cold" in ret_json:
        failure_msg = ret_json["cold"]
      if "start" in ret_json:
        start_t = ret_json["start"]
      if "end" in ret_json:
        end_t = ret_json["end"]
      else:
        success = False
        failure_msg = "Got invalid json. {} {}".format(activation_id, ret_json)

    except Exception as e:
      failure_msg = "Got exception '{}' when trying to invoke action '{}', result: '{}' - '{}'".format(e, action.url, r.status_code, r.content)
      success = False

    lat = time() - t
    failure_msg = str(failure_msg) + " : "  + str(lat) + " : " + str(activation_id) + " : " + str(start_t) + " : " + str(end_t)
    self.tm.end_transaction(success=success, transaction_name=invoke_name, failure_message=failure_msg)
 
class BurstyShape(LoadTestShape):
  spawn_rate = 5
  curr_users = 20
  # bursty = False
  length = 60*60
  inc_users = 60*5 # every 5 minutes
  last_t = 0
  inc_by = 5

  def tick(self):
    run_time = round(self.get_run_time())

    if run_time % self.inc_users == 0 and run_time != self.last_t:
      self.curr_users += self.inc_by
      print("update:", run_time, self.inc_by, self.curr_users, self.spawn_rate)
      self.last_t = run_time
    if self.curr_users > users:
      return None
    return (self.curr_users, self.spawn_rate)

class TransactionalLoad(HttpUser):
  wait_time = between(0, 1)
  host = host
  tasks = [TransactionalWaitForFunctionCoplete]
