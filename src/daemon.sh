#!/bin/bash

service cron start  
service cron status

/bin/bash /opt/sql/populate.sh
python3 /opt/collector/collector.py --downloader=cpp --config=/opt/config.ini
python3 /opt/tradingbot/bot.py --config=config.ini