# Remember

## Building & Pushing

Prep:
```bash
sudo ./gradlew distDocker -PdockerImageTag=latest -PdockerImagePrefix=alfuerst

# remember to logout or do on private machine
docker login

docker push alfuerst/invoker:latest
docker push alfuerst/controller:latest
docker push alfuerst/scheduler:latest
```

Run inside VM:
```bash
docker pull alfuerst/controller:latest
docker pull alfuerst/invoker:latest

ENVIRONMENT="bal-distrib"
redisPass='OpenWhisk'
redisPort=6379
whisk_logs_dir="/home/ow/openwhisk-logs"

cat >db_local.ini << EOL
[db_creds]
db_provider=CouchDB
db_username=OwCouch
db_password=OWCOUCH
db_protocol=http
db_host=172.29.200.161
db_port=5989

[controller]
db_provider=CouchDB
db_username=OwCouch
db_password=OWCOUCH
db_protocol=http
db_host=172.29.200.161
db_port=5989

[invoker]
db_provider=CouchDB
db_username=OwCouch
db_password=OWCOUCH
db_protocol=http
db_host=172.29.200.161
db_port=5989
EOL

ansible-playbook -i environments/$ENVIRONMENT properties.yml
ansible-playbook -i environments/$ENVIRONMENT couchdb.yml
ansible-playbook -i environments/$ENVIRONMENT initdb.yml
ansible-playbook -i environments/$ENVIRONMENT wipe.yml

ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e mode=clean -e OPENWHISK_TMP_DIR=$whisk_logs_dir
# for redis
ansible-playbook -i environments/$ENVIRONMENT apigateway.yml -e redis_port=$redisPort -e redis_pass=$redisPass
ansible-playbook -i environments/$ENVIRONMENT openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=alfuerst -e invoker_user_memory="10G" -e controller_loadbalancer_invoker_cores=6 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=2 -e controller_loadbalancer_redis_password=$redisPass -e controller_loadbalancer_redis_port=$redisPort -e invoker_redis_password=$redisPass -e invoker_redis_port=$redisPort -e limit_invocations_per_minute=10000 -e limit_invocations_concurrent=10000 -e limit_fires_per_minute=10000 -e limit_sequence_max_length=10000 -e controller_loadstrategy="LoadAvg" -e controller_algorithm="ConsistentCache" -e OPENWHISK_TMP_DIR=$whisk_logs_dir -e controller_loadbalancer_invoker_boundedceil=1.2 -e controller_activation_strategy_default="org.apache.openwhisk.core.loadBalancer.ShardingContainerPoolBalancer" -e invoker_eviction_strategy="TTL"

```

## Run simple OW thing

`{ow-home}/tools/admin/wskadmin user create afuerst`
> "dacf4133-3c3a-42d5-956c-37200c35f427:eextGdxo1jX99Uh4ms6gnS760ExMJEG3jakg0DWJ1ldqJlukrQILpbSxEA92z3Kw"

wsk property set --auth "dacf4133-3c3a-42d5-956c-37200c35f427:eextGdxo1jX99Uh4ms6gnS760ExMJEG3jakg0DWJ1ldqJlukrQILpbSxEA92z3Kw"

ow@ow-ubu-invoc:~/openwhisk-caching/ansible$ cat ~/act.py 
def main(args):
   name = args.get("name", "stranger")
   greeting = "Hello " + name + "!"
   print(greeting)
   return {"greeting": greeting}


wsk -i action create test ~/act.py 
wsk -i action invoke test -p name HELLO
