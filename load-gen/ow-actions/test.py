import os
import json
import subprocess
import requests
import time

port = 46559
docker_proc = subprocess.Popen("/usr/bin/docker run -d --cpu-shares 51 --memory 512m --memory-swap 512m --network host -e __OW_API_HOST=https://172.29.200.161 -e __OW_ALLOW_CONCURRENT=True --name AI_TEST --cap-drop NET_RAW --cap-drop NET_ADMIN --ulimit nofile=1024:1024 --pids-limit 1024 --log-driver json-file -e OW_PORT={} alfuerst/action-python-v3.6-ai:latest".format(port).split(" "))

docker_proc.wait()

time.sleep(10)

name = "video"
entrypoint="main"
with open("actions/video_processing/__main__.py") as f:
  code = f.read()

body = {"name": name, "main": entrypoint, "code":code}
body = json.dumps(body)
# print(body)
r = requests.post("http://localhost:{}/init".format(port), body)
print(r.content)

r= requests.post("http://localhost:{}/run".format(port))
print(r.content)
r = requests.post("http://localhost:{}/run".format(port))
print(r.content)

docker_proc = subprocess.Popen("/usr/bin/docker rm -f AI_TEST".split(" "))
docker_proc.wait()
