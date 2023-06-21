FROM ubuntu:20.04

RUN apt-get update && apt-get -y install vim

RUN apt-get update --fix-missing  \
       && apt-get install -y build-essential git \
       && apt-get install -y python3 python3-dev python3-setuptools \
       && apt-get install -y python3-pip \
       && apt-get install -y procps \
       && apt-get install -y tree \
	&& apt-get install -y sqlite3 \
       && apt-get install -y cron

COPY requirements.txt /tmp

RUN pip3 install --upgrade pip
RUN pip3 install -r /tmp/requirements.txt

WORKDIR /opt

ADD ./src /opt
ENV PYTHONPATH="${PYTHONPATH}:/opt"
ENV DATABASE_NAME="/opt/db/tradingbot.db"

VOLUME [ "$(pwd)/log:/tmp" ]
VOLUME [ "$(pwd)/db:/opt/db" ]

COPY /src/cron.conf /etc/cron.d/container_cronjob

RUN chmod +x cron_startup.sh
RUN chmod +x sql/populate.sh
RUN chmod +x collector/collector.py
RUN chmod +x tradingbot/bot.py

# RUN /bin/bash /opt/sql/populate.sh
RUN /bin/bash /opt/cron_startup.sh
RUN chmod +x daemon.sh

# CMD ["service", "cron", "start"]

CMD ["service", "cron", "status"]

ENTRYPOINT ["/bin/bash", "daemon.sh"]
