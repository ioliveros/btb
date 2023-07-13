import time
import json
from retry import retry

from binance.client import Client
from prettytable import PrettyTable

import datetime

class BinanceSpotAPI:
    def __init__(self, config, logger):
        self.config = config
        self.client = self.connect_client(config)
        self.supported_pairs = self.load_supported_pairs()

        self.RETRY_COUNT = 5
        self.BUFFER_TIMEOUT = 1
        self.BUFFER_MULT = 0.5

        self.logger = logger

    def load_supported_pairs(self):
        supported_pairs = {}
        with open(self.config['trading']['supported_pairs'], "r") as f:
            supported_pairs = json.loads(f.read())
        return supported_pairs

    def render_tbl(self, result, field_names):

        tbl = PrettyTable()
        tbl.field_names = field_names
        for row in result:
            field_val = []
            for k in field_names:
                field_val.append(row.get(k, "-"))
            if field_val:
                tbl.add_row(field_val)

        self.logger.info(f"\n{tbl}")
    
    def connect_client(self, config) -> object:
        creds = config['credentials']
        if config['settings']['trading_mode'] == 'test':
            return Client(
                api_key=creds['binance_api_key'], api_secret=creds['binance_api_secret'], testnet=True
            )
        else:            
            return Client(
                api_key=creds['binance_api_key'], api_secret=creds['binance_api_secret']
            )
    
    @retry(tries=3, delay=2)
    def get_prices(self, symbol):
        return self.client.get_avg_price(symbol=symbol)

    @retry(tries=3, delay=2)
    def set_order(self, symbol:str, side:str, stype:str, quantity:float, price:float, timeInForce:str=None):

        if not timeInForce:
            timeInForce = "GTC"

        if not side:
            side = "BUY"

        if not stype:
            stype = "LIMIT"

        params = {}
        params['symbol'] = symbol
        params['side'] = side
        params['type'] = stype
        params['timeInForce'] = timeInForce
        params['quantity'] = quantity
        params['price'] = price

        self.logger.debug(f"[set_order] - params: {params}")
        result = self.client.create_order(**params)
        self.render_tbl(result=[result], 
            field_names=['symbol', 'orderId', 'type', 'side', 'transactTime', 'price', 'origQty', 'executedQty', 'status']
        )
        self.logger.debug(f"[set_order] - result: {json.dumps(result, indent=2)}")
        return result     

    @retry(tries=3, delay=2)
    def close_order(self, symbol:str, side:str, stype:str, quantity:float, price:float):

        if not side:
            side = "SELL"

        if not stype:
            stype = "LIMIT"

        params = {}
        params['symbol'] = symbol
        params['side'] = side
        params['type'] = stype
        params['timeInForce'] = "GTC"
        params['quantity'] = quantity
        params['price'] = price

        self.logger.debug(f"[close_order] - params: {params}")
        result = self.client.create_order(**params)
        self.render_tbl(result=[result],
            field_names=['symbol', 'orderId', 'type', 'side', 'transactTime', 'price', 'origQty', 'executedQty', 'status']
        )
        self.logger.debug(f"[close_order] - result: {result}")
        return result

    @retry(tries=3, delay=2)
    def get_order_details(self, symbol:str, orderId:int=None):

        params = {}
        params['symbol'] = symbol
        if orderId:
            params['orderId'] = orderId

        result = self.client.get_order(**params)
        
        self.logger.info("[order details]")
        self.logger.info(f"result - {result}")
        self.render_tbl(result=[result], 
            field_names=[
                'symbol', 'orderId', 'type', 'side', 'updateTime', 'price', 
                'origQuoteOrderQty', 'origQty', 'executedQty', 'status'
            ]
        )
        return result
        
    @retry(tries=3, delay=2)
    def get_current_position(self, symbol:str):
        return self.client.get_avg_price(symbol=symbol)
        
    def get_order_book(self, amount:int, symbol:str, position_type:str, index:int=None, limit:int=None):

        self.logger.info(f"[get_order_book] - index:{index}")
        if not limit:
            limit = 10
        
        if index is None:
            if position_type == "bid":
                index = 0
            if position_type == "ask":
                index = 9

        orderbook = self.client.get_order_book(symbol=symbol, limit=limit)
        self.logger.info(f"Trading Pair: {symbol} - index:{index}")
        tbl = PrettyTable()

        if position_type == "bid":
            tbl.field_names = ["idx", "bid", "bid_quantity"]
        elif position_type == "ask":
            tbl.field_names = ["idx", "ask", "ask_quantity"]
        
        idx = 0
        for b, a in zip(orderbook["bids"], orderbook["asks"]):

            if idx == index:
                if position_type == "bid":
                    tbl.add_row([idx, str("=>")+str(b[0])+str("<="), b[1]])
                elif position_type == "ask":
                    tbl.add_row([idx, str("=>")+str(a[0])+str("<="), a[1]])
            else:
                if position_type == "bid":
                    tbl.add_row([idx, b[0], b[1]])
                elif position_type == "ask":
                    tbl.add_row([idx, a[0], a[1]])
            idx += 1

        self.logger.info(f"\n{tbl}")
        order = None
        if position_type == "bid":
            order = orderbook["bids"][index][0]
            self.logger.info(f"Buy Bid: {order} - Amount: {amount}")
        elif position_type == "ask":
            order = orderbook["asks"][index][0]
            self.logger.info(f"Sell Ask: {order} - Amount: {amount}")
        
        return order

    @retry(tries=3, delay=2)
    def cancel_order(self, symbol:str, orderId:int) -> dict:
        return self.client.cancel_order(symbol=symbol, orderId=orderId)
    
    def show_account(self, symbol:str=None) -> str:
        
        result = self.client.get_account()
        balances = result["balances"]

        tbl_results = []
        for row in balances:
            if symbol:
                if symbol.upper() == row['asset'].upper():
                    tbl_results.append({"asset": row["asset"],"free": row["free"],"locked": row["locked"]})
                    break
            else:
                if float(row["free"]) > 0 or float(row["locked"]) > 0:
                    tbl_results.append({"asset": row["asset"],"free": row["free"],"locked": row["locked"]})

        self.logger.info(f"[account] - {result['accountType']}")
        self.render_tbl(result=tbl_results, 
            field_names=["asset", "free", "locked"]
        )
        return result

    def get_symbol_info(self, trading_pair:str) -> dict:
        return self.client.get_symbol_info(trading_pair)
    
    def get_open_orders(self, symbol:str) -> dict:
        return self.client.get_open_orders(symbol=symbol)