FROM ubuntu:20.04

RUN apt-get update && apt-get -y install vim
# Update python, Install virtualenv, nginx, supervisor
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

ENTRYPOINT ["/usr/bin/python3.8", "daemon.py"]
