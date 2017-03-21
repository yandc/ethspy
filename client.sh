#!/bin/bash

if [ $1 = 'install' ]; then
	sudo easy_install selenium
	sudo cp ./chromedriver /usr/local/bin/
elif [ $1 = 'stop' ]; then
	ps x | grep ethspyClient.py | grep -v grep | awk '{print $1}' | xargs kill -9
elif [ $1 = 'start' ]; then
	nohup python ethspyClient.py > client.log &
elif [ $1 = 'status' ]; then
	ps x | grep ethspyClient.py | grep -v grep
else
	echo 'client.sh install|start|stop|status'
fi