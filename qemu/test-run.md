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
nsible-playbook -i environments/bal-distrib openwhisk.yml -e mode=clean &&  ansible-playbook -i environments/bal-distrib controller.yml -e docker_image_tag=latest -e docker_image_prefix=alfuerst -e invoker_user_memory="5120m" -e controller_loadbalancer_invoker_cores=5 -e invoker_use_runc=false -e controller_loadbalancer_invoker_c=2

ansible-playbook -i environments/bal-distrib openwhisk.yml -e docker_image_tag=latest -e docker_image_prefix=alfuerst > runlogs/distrib-ow.txt
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
