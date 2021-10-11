from wsk_interact import *
import os
from time import time, sleep
from concurrent.futures import ThreadPoolExecutor

host="https://172.29.200.161"

set_properties(host=host, auth="4d5ab701-00e1-4b60-8276-5c16e9e79a3c:TGYBjoORj3RSgOv321lLfTTh0wNT4XfGYGUMsBXoxWfZgUaEdOhOhvZKltTSdqtx")

pool = ThreadPoolExecutor()

for zip_file, action_name, container, memory in zip(zips, actions, containers, mem):
    path = os.path.join("../py", zip_file)
    # add_action(action_name, path, container, memory=memory)
    url = add_web_action(action_name, path, container, memory=memory, host=host, silent=False)
    future = invoke_web_action_async(url, pool)
    print(future.result())
    future = invoke_web_action_async(url, pool)
    print(future.result())
    # break
