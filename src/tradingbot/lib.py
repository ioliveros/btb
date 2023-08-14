import math
import random
import time
import json
import traceback
from db import SQLiteDB
from models import PredTable, TradingTable

from api.binance_futures import BinanceFuturesAPI
from api.binance_spot import BinanceSpotAPI

from decimal import Decimal, getcontext

SLEEP_BUFFER_MIN=0.01
SLEEP_BUFFER_MAX=5

class TradingBotClient:
    def __init__(self, logger, **config):

        self.config = config
        self.sdk = config['settings']['sdk']
        self.logger = logger

        self.client = self.load_sdk_client(sdk=self.sdk)
        self.db = SQLiteDB(db=config['database']['dbname'], logger=logger)

        tf_conf = config['trading']
        self.trading_pair = tf_conf['trading_pair']
        self.amount = float(tf_conf['amount']) if tf_conf['amount'] else 0
        self.trade_type = tf_conf["trade_type"]

        self.trd_tbl = TradingTable(self.logger)
        self.trading_info = self.client.get_symbol_info(trading_pair=self.trading_pair)
        self.logger.info(f"[trading_filter] - {json.dumps(self.trading_info, indent=2)}")

        self.base_asset_precision = self.trading_info["baseAssetPrecision"]
        self.quote_precision = self.trading_info["quotePrecision"]
        self.step_size = float(self.get_filter_value("LOT_SIZE", "stepSize"))
        self.tick_size = float(self.get_filter_value("PRICE_FILTER", "tickSize"))

        self.sleep_buffer_min = SLEEP_BUFFER_MIN
        self.sleep_buffer_max = SLEEP_BUFFER_MAX

    def load_sdk_client(self, sdk):
        if sdk == 'binance_futures':
            return BinanceFuturesAPI(**self.config)
        elif sdk == 'binance_spot':
            return BinanceSpotAPI(self.config, self.logger)
        else:
            self.logger.debug(f"SDK not supported")

    def buffer(self) -> None:
        sleep_time = random.uniform(self.sleep_buffer_min, self.sleep_buffer_max)
        self.logger.debug(f"sleep .. {sleep_time}")
        time.sleep(sleep_time)

    def get_filter_value(self, filter_type, filter_attr):

        filter_value = None 
        for item in self.trading_info['filters']:
            if item["filterType"] == filter_type:
                filter_value = item[filter_attr]
                break
        return filter_value

    def get_prices(self, symbol):
        return self.client.get_prices(symbol=symbol)

    def set_order(self, symbol:str, side:str, stype:str, quantity:float, 
                                        price:float, timeInForce:str=None):
        
        if not self.client.supported_pairs.get(symbol, None):
            self.logger.debug(f"Current sdk doesn't support this pair: {symbol}")
            return

        if self.trade_type == "futures":
            return self.client.set_order(
                    symbol=symbol, side=side, type=stype, 
                    quantity=quantity, price=price, timeInForce=timeInForce
                )
        elif self.trade_type == "spot":
            return self.client.set_order(
                    symbol=symbol, side="BUY", stype="LIMIT", 
                    quantity=quantity, price=price, timeInForce="GTC"
                )
    
    def get_order_details(self, symbol:str, timestamp:int=None, orderId:int=None, 
                                origClientOrderId:str=None, recvWindow:int=None):
        
        if self.trade_type == "futures":
            return self.client.get_order_details(symbol=symbol, timestamp=timestamp, orderId=orderId)

        elif self.trade_type == "spot":
            return self.client.get_order_details(symbol=symbol, orderId=orderId)

    def get_current_position(self, symbol=str):
        return self.client.get_current_position(symbol=symbol)

    def close_order(self, symbol:str, side:str, stype:str, quantity:float, reduceOnly:str=None, price:int=None):

        if self.trade_type == "futures":
            return self.client.close_order(
                symbol=symbol, side=side, type=type, 
                quantity=quantity, reduceOnly=reduceOnly
            )
        elif self.trade_type == "spot":

            # set precision
            getcontext().prec = self.base_asset_precision

            quantity = "{:.{precision}f}".format(Decimal(quantity), precision=self.base_asset_precision)
            while True:
                self.logger.info(f"[close_order] - quantity:{quantity} - price:{price}")
                try:
                    return self.client.close_order(
                                symbol=symbol, side="SELL", stype=stype, 
                                quantity=quantity, price=price
                            )
                except:       
                    
                    log_error = traceback.format_exc()
                    if 'insufficient balance for requested action' in log_error:
                        # trim down order
                        remaining_quantity = self.check_remaining_coins(symbol, quantity)
                        adjusted_q = Decimal(remaining_quantity) - Decimal(self.step_size)
                        quantity = "{:.{precision}f}".format(adjusted_q, precision=self.base_asset_precision)                        

                    if 'Precision' in log_error:
                        # adjust precision                        
                        quantity = "{:.{precision}f}".format(Decimal(quantity), precision=self.base_asset_precision)

                    if 'Filter failure: LOT_SIZE' in log_error:
                        # adjust sell_amount to correct LOT_SIZE
                        adjusted_q = math.floor(Decimal(quantity))
                        quantity = "{:.{precision}f}".format(adjusted_q, precision=self.base_asset_precision)
                    
                    else:
                        self.logger.warning(f"[close_order] - {log_error}")

                self.buffer()                                    

    def save_requested_position(self, data:dict, render:bool=None):
        if render:
            self.client.render_tbl([data], 
                field_names=[
                    "transactionId", "orderId", "sellId", "unrealizedProfit", "currentPrice", "realizedProfit",
                    "buyPrice", "sellPrice", "status", "isExpired", "actualBuyQty", "actualSellQty", "amount"
                ]
            )
        return self.trd_tbl.save_requested_position(db=self.db, data=data)

    def get_predictions(self, symbol:str):
        tbl = PredTable() 
        result = tbl.get_predictions(db=self.db, symbol=symbol)
        return tbl.deserialize(result)

    def get_position_data(self, symbol:str, tty:str, orderId:int=None):
        return self.trd_tbl.get_position_data(db=self.db, symbol=symbol, tty=tty, orderId=orderId)

    def expire_requested_position(self, orderId:str):
        return self.trd_tbl.expire_requested_position(db=self.db, orderId=orderId)

    def get_current_position_data(self, orderId:str):
        return self.trd_tbl.get_current_position_data(db=self.db, orderId=orderId)

    def mark_position_closed(self, transactionId:int):
        return self.trd_tbl.mark_position_closed(db=self.db, transactionId=transactionId)

    def cancel_order(self, symbol:str, orderId:str=None):
        if self.trade_type == "futures":
            return self.client.cancel_order(symbol=symbol)
        elif self.trade_type == "spot":
            try:
                return self.client.cancel_order(symbol=symbol, orderId=orderId)
            except Exception as err:
                self.logger.warning(f"cancelled order - symbol:{symbol} - orderId:{orderId} - warning:{err}")
                # do some cleanup
                self.cancel_open_orders(symbol)
                return {
                    "orderId": orderId,
                    "status": "CANCELED"
                }

    def mark_position_cancelled(self, transactionId:int):
        return self.trd_tbl.mark_position_cancelled(db=self.db, transactionId=transactionId)
    
    def get_order_book(self, amount:int, symbol:str, position_type:str, index:int=None, limit:int=None):
        if not limit:
            limit = 10

        return self.client.get_order_book(
            amount=amount, symbol=symbol, position_type=position_type, index=index, limit=limit
        )
    
    def show_account(self, symbol:str=None):
        return self.client.show_account(symbol)
    
    def get_order_status(self, transactionId:int):
        return self.trd_tbl.get_order_status(db=self.db, transactionId=transactionId)
    
    def get_profit(self, transactionId:int, bid_price=None, sell_price=None) -> float:

        unrealizedProfit = None
        realizedProfit = None
        buyPriceValue = None
        sellPriceValue = None

        price_data = self.get_prices(symbol=self.trading_pair)
        orderData = self.get_order_status(transactionId)

        # set precision
        getcontext().prec = self.base_asset_precision

        if bid_price:            
            # compute for the current profit
            buyPriceValue = Decimal(orderData['abq']) * Decimal(bid_price)
            currentPriceValue = Decimal(orderData['abq']) * Decimal(price_data["price"])            
            # unrealized profit
            uP = currentPriceValue - buyPriceValue            
            unrealizedProfit = "{:.{precision}f}".format(uP, precision=self.base_asset_precision)

        if sell_price:

            # compute for the current profit                        
            buyPriceValue = Decimal(orderData['abq']) * Decimal(bid_price)
            currentPriceValue = Decimal(orderData['abq']) * Decimal(price_data["price"])            
            sellPriceValue = Decimal(orderData['asq']) * Decimal(sell_price)            

            # unrealized profit
            uP = Decimal(currentPriceValue) - Decimal(buyPriceValue)
            unrealizedProfit = "{:.{precision}f}".format(uP, precision=self.base_asset_precision)
            self.logger.info(f"[get_profit] => unrealizedProfit: {currentPriceValue} - {buyPriceValue} = {unrealizedProfit}")

            # actual realized profit            
            rP = Decimal(sellPriceValue) - Decimal(buyPriceValue)
            realizedProfit = "{:.{precision}f}".format(rP, precision=self.base_asset_precision)
            self.logger.info(f"[get_profit] => realizedProfit: {sellPriceValue} - {buyPriceValue} = {realizedProfit}")

        return {            
            "buyPriceValue": buyPriceValue,            
            "sellPriceValue": sellPriceValue,
            "unrealizedProfit": unrealizedProfit,
            "currentPrice": price_data["price"],
            "realizedProfit": realizedProfit
        }

    def render_tbl(self, result, field_names):
        self.client.render_tbl(result, field_names=field_names)

    def is_allowed_lotsize(self, trading_pair:str, amount:float) -> bool:

        is_allowed = True
        min_lotsize = None
        max_lotsize = None
        step_size = None

        if not self.trading_info:
            self.logger.warning(f"trading pair not supported - {trading_pair}")
            return False

        for d in self.trading_info["filters"]:
            if d["filterType"] == "LOT_SIZE":
                min_lotsize = float(d['minQty'])
                max_lotsize = float(d['maxQty'])
                step_size = float(d['stepSize'])

        if min_lotsize and max_lotsize and step_size:
            if float(amount) < min_lotsize:
                self.logger.warning(f"Amount: {amount} is less than min allowed LOT_SIZE: {min_lotsize}")
                return False            
            if float(amount) > max_lotsize:
                self.logger.warning(f"Amount: {amount} is greater than max allowed LOT_SIZE: {max_lotsize}")
                return False
            
            # # (quantity - minQty) % stepSize == 0
            # cstep_size = (float(amount) - float(min_lotsize))
            # if cstep_size % float(step_size) != 0:
            #     self.logger.warning(f"Computed size: {cstep_size} doesn't match allowed STEP_SIZE: {step_size}")
            #     return False

        return is_allowed
    
    def is_allowed_notional_size(self, trading_pair:str, amount:float, price:float) -> bool:

        is_allowed = True
        min_notional_size = None
        max_notional_size = None

        if not self.trading_info:
            self.logger.warning(f"trading pair not supported - {trading_pair}")
            return False
        
        for d in self.trading_info["filters"]:
            if d["filterType"] == "NOTIONAL":
                min_notional_size = float(d['minNotional'])
                max_notional_size = float(d['maxNotional'])
        
        if min_notional_size and max_notional_size:
            # 19000 x 0.00002 = 0.38 < 10 (MIN_NOTIONAL.minNotional)
            notional_size = float(price) * float(amount)
            if float(notional_size) < min_notional_size:
                self.logger.warning(f"Price: {price} x Amount: {amount} = {notional_size} is less than min allowed NOTIONAL_SIZE: {min_notional_size}")
                return False
            if float(notional_size) > max_notional_size: 
                self.logger.warning(f"Price: {price} x Amount: {amount} = {notional_size} is greater than max allowed NOTIONAL_SIZE: {max_notional_size}")
                return False

        return is_allowed
        
    def cancel_open_orders(self, symbol:str) -> None:
        self.logger.info(f"checking for open orders..")
        orders = self.client.get_open_orders(symbol=symbol)
        for order in orders:
            oId = order['orderId']
            self.logger.info(f"cancelling open order symbol:{symbol} - orderId:{oId} ")
            self.client.cancel_order(symbol=symbol, orderId=oId)

    def get_trimmed_quantity(self, quantity):

        if not self.trading_info:
            self.logger.warning(f"trading pair not supported - {self.trading_pair}")
            return False
        
        trimmed_quantity = math.floor((float(quantity) / float(self.step_size)) * float(self.step_size))
        return trimmed_quantity

    def get_trimmed_price_precision(self, price):

        if not self.trading_info:
            self.logger.warning(f"trading pair not supported - {self.trading_pair}")
            return False
    
        trimmed_price = round(price / self.tick_size) * self.tick_size
        return trimmed_price


    def check_remaining_coins(self, symbol:str, sell_amount:int) -> int:

        result = self.client.show_account(symbol)
        if not result:
            return sell_amount

        remaining_coins = 0
        for row in result["balances"]:
            if symbol.upper() != row['asset'].upper(): continue
            remaining_coins = row["free"]
            break


        updated_sell_amount = 0
        getcontext().prec = self.base_asset_precision
        if Decimal(sell_amount) < Decimal(remaining_coins):
            remaining_coins_plus_sell_amount = "{:.{precision}f}".format(Decimal(remaining_coins), precision=self.base_asset_precision)
            updated_sell_amount = Decimal(remaining_coins)
        else:            
            if Decimal(sell_amount) == Decimal(remaining_coins):
                updated_sell_amount = Decimal(sell_amount)
            else:
                updated_sell_amount = Decimal(remaining_coins)
        
        s_updated_sell_amount = "{:.{precision}f}".format(updated_sell_amount, precision=self.base_asset_precision)
        self.logger.info(f"[check_remaining_coins] -  final -> {s_updated_sell_amount}")

        return s_updated_sell_amount

        