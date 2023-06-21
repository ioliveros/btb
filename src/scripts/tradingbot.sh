#!/bin/bash

set +x

export PYTHONPATH=$PYTHONPATH:/$BASE

BASE=/opt
CONFIG=$1

if [[ -z "$1" ]]
then
	CONFIG=/opt/config.ini
fi


echo $(date +"%F %H %M:%S") "[bot] running collector bot .."
python3 $BASE/collector/collector.py --downloader=cpp --config=$CONFIG

echo $(date +"%F %H %M:%S") "[bot] get order .."
python3 $BASE/tradingbot/app.py --option=order --config=$CONFIG

echo $(date +"%F %H %M:%S") "[bot] check if closing order .."
python3 $BASE/tradingbot/app.py --option=close_order --config=$CONFIG

echo $(date +"%F %H %M:%S") '[bot] done ..'
