#!/bin/bash

touch /var/log/cron.log

(crontab -l ; echo "* * * * * /usr/bin/python3 /opt/collector/collector.py --downloader=cpp --config=/opt/config.ini >> /tmp/collector.log 2>&1")| crontab

service cron start  
service cron status

# /usr/bin/python3 /opt/collector/collector.py --downloader=cpp --config=/opt/config.ini