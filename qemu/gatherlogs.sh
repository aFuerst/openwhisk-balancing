
# VMs at IPs 172.29.200.161 & 172.29.200.166-8

user='ow'
pw='OwUser'

sshpass -p $pw scp "$user@172.29.200.161:/home/ow/openwhisk-logs/wsklogs/controller0/controller0_logs.log" ./systemlogs

for VMID in 6 7 8
do

INVOKERID=0

if [ $VMID == 7 ]
then
INVOKERID=1
elif [ $VMID == 8 ]
then
INVOKERID=2
fi

name="invoker$INVOKERID"
pth="/home/ow/openwhisk-logs/wsklogs/"
pth+="$name/"
pth+="$name"
pth+="_logs.log"
sshpass -p $pw scp "$user@172.29.200.16$VMID:$pth" ./systemlogs

done