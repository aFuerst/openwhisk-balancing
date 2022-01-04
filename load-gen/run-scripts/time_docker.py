import numpy as np
import subprocess
import requests
from time import time

port_start = 40000
base_cmd = "/usr/bin/docker run -d --cpu-shares 51 --memory 512m --memory-swap 512m --network host -e __OW_API_HOST=https://172.29.200.161 -e __OW_ALLOW_CONCURRENT=True --name TEST_{} --cap-drop NET_RAW --cap-drop NET_ADMIN --ulimit nofile=1024:1024 --pids-limit 1024 --log-driver json-file -e OW_PORT={} alfuerst/action-python-v3.6-ai:latest"

nopause_times = []

for i in range(50):
  port = port_start + i
  start = time()
  docker_proc = subprocess.Popen(base_cmd.format(i, port).split(" "), stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
  docker_proc.wait()
  end = time()
  nopause_times.append(end-start)

for i in range(50):
  docker_proc = subprocess.Popen("/usr/bin/docker rm -f TEST_{}".format(i).split(" "), stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
  docker_proc.wait()

print("nopause =", nopause_times)
print("nopause_quants = ", np.quantile(nopause_times, [0.1, 0.5, 0.9, 0.99]))
pause_times = []

for i in range(50):
  port = port_start + i
  start = time()
  docker_proc = subprocess.Popen(base_cmd.format(i, port).split(
      " "), stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
  docker_proc.wait()
  end = time()

  docker_proc = subprocess.Popen("/usr/bin/docker pause TEST_{}".format(i).split(" "), stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
  docker_proc.wait()

  pause_times.append(end-start)

print("pause =", pause_times)
print("pause_quants =", np.quantile(pause_times, [0.1, 0.5, 0.9, 0.99]))

# nopause: [0.8424656391143799, 0.8794686794281006, 0.8383574485778809, 0.8385422229766846, 0.845935583114624, 0.8694543838500977, 0.8701872825622559, 0.930682897567749, 0.8463730812072754, 0.9475095272064209, 0.8871216773986816, 0.9296097755432129, 0.9066681861877441, 0.9212923049926758, 0.9390304088592529, 0.9205105304718018, 0.8975439071655273, 0.8874044418334961, 0.8710124492645264, 0.8958873748779297, 0.897958517074585, 0.8638732433319092, 0.8797342777252197, 0.8391029834747314, 0.9796590805053711, 0.8379769325256348, 0.9228849411010742, 0.8961644172668457, 0.9389557838439941, 0.936150312423706, 0.9874045848846436, 0.9963040351867676, 1.013368844985962, 0.9723410606384277, 1.0047473907470703, 1.247323989868164, 0.9541144371032715, 0.9881720542907715, 0.9575178623199463, 0.9805879592895508, 0.9471685886383057, 0.9790425300598145, 0.9224715232849121, 0.9550325870513916, 0.9468245506286621, 0.9210259914398193, 0.9519765377044678, 0.913637638092041, 0.9306991100311279, 0.9727966785430908]
# np_quantiles = [0.84558859 0.92267823 0.98748133 1.13268597]

for i in range(50):
  docker_proc = subprocess.Popen("/usr/bin/docker rm -f TEST_{}".format(i).split(
      " "), stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
  docker_proc.wait()
