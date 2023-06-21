#!/bin/bash

set +e

symbol=$1
image_name=btb-$symbol:latest
container_name=btb-$symbol

# create directory if not exists
if [[ ! -e "db" ]]; then
    mkdir db
fi

if [[ ! -e "log" ]]; then
    mkdir log
fi

docker rmi -f $(docker images -f "dangling=true" -q)

docker rm $container_name
docker build -t $image_name -f Dockerfile .


if [ $2 == '-d' ];then
	echo 'Run detach mode'
	docker run -d --name $container_name --hostname $container_name -v $(pwd)/log:/tmp -v $(pwd)/db:/opt/db $image_name
else
	echo 'Run non-detach'
	docker run --name $container_name --hostname $container_name -v $(pwd)/log:/tmp -v $(pwd)/db:/opt/db $image_name
fi
