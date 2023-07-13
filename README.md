# Setup Trading Bot

```bash
touch xrp.config.ini
```

```bash
vim config.ini
```

## running on testnet
```
[app]
debug=1

[settings]
sdk=binance
trading_mode=test

[credentials]
binance_api_key=<api_key>
binance_api_secret=<api_secret>

[database]
dbname=/opt/db/tradingbot.db

[trading]
symbol=<cyrpto_symbol>
trading_pair=<crypto_trading_pair>
side=0
amount=0
entry_price=0
target_price=0

[feedsource]
downloader=cpp
```

# Build container

## detach mode
```bash
./build.sh <crypto_name> -d
```

## follow mode
```bash
./build.sh <crypto_name>
```

## check if running
```bash
docker logs -f btb-crypto_name
```



Enjoy! :)
