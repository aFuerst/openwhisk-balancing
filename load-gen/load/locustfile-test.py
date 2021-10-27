from locust import HttpUser, task, between
import os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


host = os.environ["HOST"]
auth = os.environ["AUTH"]


class FirstUser(HttpUser):
  wait_time = between(0, 1)
  host = host

  @task
  def hello_world(self):
    r = self.client.get("https://172.29.200.161:10001/api/v1/web/afuerst/default/hello_150", verify=False)
    print(r, type(r))
