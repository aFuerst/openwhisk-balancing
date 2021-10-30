from locust import HttpUser, task, constant, events, between, TaskSet, SequentialTaskSet
from locust_plugins.transaction_manager import TransactionManager
import little
from wsk_interact import *
import random
import os
from time import time

host = os.environ["HOST"]
auth = os.environ["AUTH"]

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




class TransactionalWaitForFunctionCoplete(SequentialTaskSet):
     
  def on_start(self):
    self.u, self.p = auth.split(":")
    self.max_wait = 10*60

    self.tm = TransactionManager()

  @task
  def invoke(self):
    action = random.choices(population=acts, weights=freqs, k=1)[0]
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
      else:
        success = False
        failure_msg = "Got invalid json. {} {}".format(activation_id, ret_json)

    except Exception as e:
      failure_msg = "Got exception '{}' when trying to invoke action '{}', result: '{}' - '{}'".format(e, action.url, r.status_code, r.content)
      success = False

    lat = time() - t
    failure_msg = str(failure_msg) + " : "  + str(lat) 
    self.tm.end_transaction(success=success, transaction_name=invoke_name, failure_message=failure_msg)
 
class TransactionalLoad(HttpUser):
  wait_time = between(0, 1)
  host = host
  tasks = [TransactionalWaitForFunctionCoplete]
