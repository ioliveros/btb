import sys
import time

import configparser

from binance.client import Client

config = configparser.ConfigParser()
config.read("config.ini")

client = Client(
			api_key=config["credentials"]["binance_api_key"],
			api_secret=config["credentials"]["binance_api_secret"],
			testnet=True
		)

symbol = config["trading"]["trading_pair"]

account = client.get_account()
print(f"[account] - {account['accountType']}")
print(f"[info] - {account}")
balances = account["balances"]
for info in balances:
	print(f"{info['asset']} - {info['free']}")

orders = client.get_open_orders(symbol=sys.argv[1])
for order in orders:
	corder = client.cancel_order(symbol=sys.argv[1], orderId=order['orderId'])
	print(f"Cancelled: {corder}")

orders = client.get_open_orders(symbol=sys.argv[1])
if orders:
	for order in orders:
		print(f"Order -> {order}")
else:
	print(f"No more open.")