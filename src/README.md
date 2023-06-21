# Build container

docker build -t <image_name> -f Dockerfile . --no-cache

# Run docker container
docker run -p 5051:5051 --name <name_of_container> --hostname <name_of_hostname> -d -v <path_to_volume>:/opt/src <image_name>

# Test Run
sudo docker build -t trading-bot -f Dockerfile . --no-cache
docker run --name tradingbot --hostname tradingbot -d trading-bot
