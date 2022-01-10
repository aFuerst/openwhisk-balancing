#!/bin/bash


$cmd="cd /home/ow/openwhisk-balancing/ansible;
ENVIRONMENT='host-distrib';
redisPass='OpenWhisk';
redisPort=6379;
whisk_logs_dir='/home/ow/openwhisk-logs';
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
EOL;
ansible-playbook -i environments/\$ENVIRONMENT properties.yml;
ansible-playbook -i environments/\$ENVIRONMENT couchdb.yml;
ansible-playbook -i environments/\$ENVIRONMENT initdb.yml;
ansible-playbook -i environments/\$ENVIRONMENT wipe.yml;
"

pw='OwUser'
IP=172.29.200.161
sshpass -p $pw ssh "ow@$IP" $cmd

AUTH=$(sshpass -p $pw ssh ow@$IP "/home/ow/openwhisk-balancing/tools/admin/wskadmin user create afuerst")
echo $AUTH
