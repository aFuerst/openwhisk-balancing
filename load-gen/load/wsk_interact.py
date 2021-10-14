import os
import subprocess
from time import time, sleep
import json
import requests
from threading import Thread
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

zips = ["chameleon.zip",  "cnn_image_classification.zip",  "dd.zip",  "float_operation.zip",  "gzip_compression.zip",  "hello.zip",  "image_processing.zip",  "lin_pack.zip",  "model_training.zip",  "pyaes.zip",  "video_processing.zip", "json_dumps_loads.zip"]
actions = ["cham", "cnn", "dd", "float", "gzip", "hello", "image", "lin_pack", "train", "aes", "video", "json"]
containers = ["python:ai-vid", "python:ai", "python:ai-vid", "python:ai", "python:3", "python:3", "python:ai", "python:ai", "python:ai", "python:ai-vid", "python:ai-vid", "python:3"]
# mem = [512, 1024, 256, 128, 128, 256, 640, 640, 512, 1024, 894, 128]
mem = [128, 512, 256, 256, 128, 128, 256, 256, 256, 128, 384, 128]
warm_times = [0.055, 1.939, 1.184, 0.044, 0.352, 0.034, 6.365, 0.049, 8.357, 0.633, 31.036, 0.279]
cold_times = [2.740, 7.725, 2.824, 2.896, 2.715, 2.251, 9.468, 2.868, 11.934, 3.000, 35.300, 2.502]
max_wait = 5*60


def set_properties(host=None, auth=None):
    if host == None:
      host = 'http://172.17.0.1:3233'
    if auth == None:
        auth = 'babecafe-cafe-babe-cafe-babecafebabe:007zO3xZCLrMN6v2BKK1dXYFpXlPkccOFqm12CdAsMgRU4VrNZ9lyGVCGuMDGIwP'
    wsk = subprocess.run(args=["wsk", "property", "set", "--apihost", host, "--auth", auth], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if wsk.returncode != 0:
        print(wsk.stderr)
        wsk.check_returncode()
    wsk = subprocess.run(args=["wsk", "package", "create", "py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def add_action(name:str, path:str, container:str="python:3", memory:int=256):
    args = ["wsk", "-i", "action", "update", name, "--memory", str(memory), "--kind", container, path]
    wsk = subprocess.run(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if wsk.returncode != 0:
        print(wsk.stderr)
        wsk.check_returncode()
    wsk.check_returncode()

def add_web_action(name:str, path:str, container:str="python:3", memory:int=256, host="http://172.17.0.1:3233", silent=True):
    url = "/afuerst/{}".format(name)
    args = ["wsk", "-i", "action", "update", url, path, "--web", "true", "--memory", str(memory), "--kind", container, "--timeout", str(5*60*1000)]
    wsk = subprocess.run(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if wsk.returncode != 0:
      print(wsk.stdout.decode())
      print(wsk.stderr.decode())
    wsk.check_returncode()

    args = ["wsk", "-i", "action", "get", url, "--url"]
    wsk = subprocess.run(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if wsk.returncode != 0:
      print(wsk.stdout.decode())
      print(wsk.stderr.decode())
    wsk.check_returncode()

    url = wsk.stdout.decode()
    url = url.split("\n")[1]
    if not silent:
      print(url)
    # print("{}/api/v1/web{}".format(host, url))
    return url

def invoke_action(name:str, act_args:dict, return_code:bool=False):
    popen_args = ["wsk", "action", "invoke", "--result", name]
    for key, value in act_args.items():
        popen_args += ["--param", str(key), str(value)]
    start = time()
    wsk = subprocess.run(args=popen_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    latency = time() - start
    if wsk.returncode != 0:
        if return_code:
            return wsk.stderr, latency, wsk.returncode
        return wsk.stderr, latency
    if return_code:
        return json.loads(wsk.stdout.decode()), latency, 0
    return json.loads(wsk.stdout.decode()), latency

def invoke_web_action(url):
    requests.get(url)

def invoke_web_action_async(url, threadpool, auth, host):
  def action(action_url, auth, host):
    start = time()
    r = requests.get(action_url, verify=False)
    latency = time() - start

    try:
      if "x-openwhisk-activation-id" in r.headers:
        activation_id = r.headers["x-openwhisk-activation-id"]
      else:
        activation_id="ERROR"
      if r.status_code == 502:
        return None, 0, "{ }", str(r.status_code)
      if r.status_code == 202:
        # invocation timed out, poll for result
        # https://172.29.200.161/api/v1/namespaces/_/activations/7f6564cf8c5f494da564cf8c5fd94d3f
        resp_json = r.json()
        # print("202 JSON:", resp_json)
        poll_url = "https://172.29.200.161/api/v1/namespaces/_/activations/{}".format(activation_id)
        u,p = auth.split(":")
        i = 0
        r = requests.get(poll_url, verify=False, auth=(u,p))
        while r.status_code != 200 and i < max_wait:
          if r.status_code == 502:
            return None, 0, "{ }", str(r.status_code)
          # if new_r.status_code == 404:
          #   print("Got 404 trying to look for activation ID {} from request JSON {} and headers {}".format(activation_id, resp_json, r.headers))
          #   return None, 0, "{ }", ""
          sleep(2)
          r = requests.get(poll_url, verify=False, auth=(u,p))
          i += 1
        latency = time() - start
        if i == max_wait:
          print("Activation with ID {} failed to finish reasonbly. {}".format(activation_id, resp_json))
          return None, 0, "{ }", str(r.status_code)
        # print("second route headers: {} json: {}\n".format(new_r.headers, new_r.json()))
        ret_json = r.json()
        if "response" in ret_json and "result" in ret_json["response"] and "body" in ret_json["response"]["result"]:
          ret_json = ret_json["response"]["result"]["body"]
      else:
        ret_json = r.json()
      if "cold" in ret_json:
        was_cold = ret_json["cold"]
      else:
        print("got invalid json", r.status_code, ret_json)
        was_cold = None
    except Exception as e:
      print("Got exception '{}' when trying to invoke action '{}', result: '{}' - '{}'".format(e, action_url, r.status_code, r.content))
      raise e
      return None, 0, "{ }", "UNKNOWN"

    return was_cold, latency, ret_json, activation_id

  return threadpool.submit(action, url, auth, host)


def invoke_action_async(name:str, act_args:dict):
    """
    Returns a tuple of running Popen object and the timestamp of when it was started
    """
    popen_args = ["wsk", "action", "invoke", "--result", name]
    for key, value in act_args.items():
        popen_args += ["--param", str(key), str(value)]
    start = time()
    wsk = subprocess.Popen(args=popen_args)
    # print(wsk)
    return wsk, start
    # latency = time() - start
    # if wsk.returncode != 0:
    #     return wsk.stderr, latency
    # return json.loads(wsk.stdout.decode()), latency

def wait_all_popen(procs):
    """
    wait for a list or Popen objects to finish
    """
    for proc, start in procs:
        proc.wait()
        # print(proc.stdout.read())

if __name__ == "__main__":
    set_properties()
    for zip_file, action_name, container, memory in zip(zips, actions, containers, mem):
        path = os.path.join("../py", zip_file)
        add_action(action_name, path, container, memory=memory)
        ret_json, latency = invoke_action(action_name, {})
        print(ret_json, latency)

    add_action("js_act_1", "../js/hello.js", container="nodejs:10")
    p = invoke_action_async("js_act_1", {"name":"ben"})
    wait_all_popen([p])
    print("async", p)
    print(invoke_action("js_act_1", {"name":"ben"}))