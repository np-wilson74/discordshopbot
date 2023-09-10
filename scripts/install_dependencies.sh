#!/bin/bash
# This file is scripts/install_dependencies.sh

#yum install python
#curl -O https://bootstrap.pypa.io/get-pip.py
#python3 get-pip.py --user
#echo "export PATH=LOCAL_PATH:$PATH" >> ~/.bash_profile
#source ~/.bash_profile
python3 -m pip install -r /home/ec2-user/scripts/requirements.txt
sudo chmod 666 /home/ec2-user/config.json
sudo chmod 666 /home/ec2-user/logs/*
if [ $(ps -ef | grep main.py | awk '{print $2}' | wc -l) -ge 2 ]; then
    for PID in $(ps -ef | grep main.py | awk '{print $2}' | head -n 1 ); do kill -9 $PID; done;
fi
