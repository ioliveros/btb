import time
import json
from retry import retry

from binance.client import Client


class BinanceFuturesAPI:
    def __init__(self, **config):
        
        self.config = config
        self.client = self.connect_client(**config['credentials'])
        self.supported_pairs = self.load_supported_pairs()

        self.RETRY_COUNT = 5
        self.BUFFER_TIMEOUT = 1
        self.BUFFER_MULT = 0.5

        self.set_leverage(config)        

    def load_supported_pairs(self):
        supported_pairs = {}
        with open(self.config['trading']['supported_pairs'], "r") as f:
            supported_pairs = json.loads(f.read())
        return supported_pairs

    def connect_client(self, **config) -> object:
        if config['settings']['trading_mode'] == 'test':
            return Client(
                api_key=config['binance_api_key'], api_secret=config['binance_api_secret'], testnet=True
            )
        else:
            return Client(
                api_key=config['binance_api_key'], api_secret=config['binance_api_secret']
            )

    @retry(tries=3, delay=2)
    def set_leverage(self, config:dict) -> None:
        # need to set a default leverage
        self.client.futures_change_leverage(
            symbol=config['trading']['trading_pair'], leverage=1
        )

    @retry(tries=3, delay=2)
    def get_prices(self, symbol):
        return self.client.get_avg_price(symbol=symbol)

    @retry(tries=3, delay=2)        
    def set_order(self, symbol:str, side:str, type:str, quantity:float, price:float, timeInForce:str=None):

        params = {}
        if not timeInForce:
            timeInForce = "GTC"

        params['symbol'] = symbol
        params['side'] = side
        params['type'] = type
        params['quantity'] = quantity
        params['price'] = price
        params['timeInForce'] = timeInForce

        print(f"[set_order] - {params}")
        return self.client.futures_create_order(**params)        

    @retry(tries=3, delay=2)
    def close_order(self, symbol:str, side:str, type:str, quantity:float, reduceOnly:str=None):

        params = {}
        if not reduceOnly:
            params['reduceOnly'] = 'true'

        # flip side to close specific position
        if side == "BUY":
            params['side'] = "SELL"
        else:
            params['side'] = "BUY"

        params['symbol'] = symbol
        params['type'] = type
        params['quantity'] = quantity
        
        return self.client.futures_create_order(**params)

    @retry(tries=3, delay=2)
    def get_order_details(self, symbol:str, timestamp:int, orderId:int=None, origClientOrderId:str=None, recvWindow:int=None):

        params = {}
        params['symbol'] = symbol
        #params['timestamp'] = timestamp

        if orderId:
            params['orderId'] = orderId

        if  origClientOrderId:
            params['origClientOrderId'] =  origClientOrderId

        if recvWindow:
            params['recvWindow'] = recvWindow
        
        return self.client.futures_get_order(**params)
        
    @retry(tries=3, delay=2)
    def get_current_position(self, symbol:str):
        result = {}
        positions = self.client.futures_account()['positions']
        for item in positions:
            if item['symbol'] != symbol: continue
            iM = float(item['initialMargin'])
            uP = float(item['unrealizedProfit'])
            result['updateTime'] = item['updateTime']
            result['initialMargin'] = iM
            result['unrealizedProfit'] = uP
            result['roE'] = (uP / iM) * 100
            break
        return result

    @retry(tries=3, delay=2)
    def cancel_order(self, symbol:str) -> dict:
        return self.client.futures_cancel_all_open_orders(symbol=symbol)
