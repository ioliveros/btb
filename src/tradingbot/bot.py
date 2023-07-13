import json
import sys
import configparser
import argparse
import time
import traceback

import random
from random import randint

from utils import Monitoring
from lib import TradingBotClient

DEFAULT_LOGNAME="tradingbot"
DEFAULT_LOGDIR="/tmp"
DEFAULT_BUY_DELAY = 0
DEFAULT_BID_RETRY = 5
DEFAULT_SELL_RETRY = 20
DEFAULT_SELL_INDEX = 9
DEFAULT_BYPASS_ELAPSED_TIME_EXP=0
DEFAULT_ELAPSED_TIME_EXP=60

SLEEP_BUFFER_MIN=0.01
SLEEP_BUFFER_MAX=5

BACK_OFF_START_COUNT=1
BACK_OFF_MULTIPLIER=0.5
BACK_OFF_LIMIT=100

class Bot:

    def __init__(self, config):

        self.config = config
        
        # bot settings
        self.run_forever = int(config['settings']['run_forever'])
        self.logdir = config['settings'].get("logdir", DEFAULT_LOGDIR)
        self.logname = config['trading']['trading_pair'].lower()

        # logging
        log = Monitoring(logdir=self.logdir, debug=int(config['app']['debug']))
        self.logger = log.get_logger(self.logname)

        # sleep buffers
        self.sleep_buffer_min = float(config['settings'].get('sleep_buffer_min', SLEEP_BUFFER_MIN))
        self.sleep_buffer_max = float(config['settings'].get('sleep_buffer_max', SLEEP_BUFFER_MAX))
        self.back_off_start_count = float(config['settings'].get('back_off_start_count', BACK_OFF_START_COUNT))

        # get tradingpair info
        self.bot = TradingBotClient(self.logger, **config)

        # trade settings
        self.buy_delay = int(config['trading'].get('buy_delay', DEFAULT_BUY_DELAY))
        self.trade_type = config['trading']['trade_type']
        self.symbol = config['trading']['symbol']
        self.trading_pair = config['trading']['trading_pair']
        self.amount = config['trading']['amount']
        
        # bid config
        self.bid_retry = int(config['trading'].get('bid_retry', DEFAULT_BID_RETRY))
        self.sell_retry = int(config['trading'].get('sell_retry', DEFAULT_SELL_RETRY))

        # sell config
        self.sell_index = int(config['trading'].get('sell_index', DEFAULT_SELL_INDEX))

        self.bypass_elapsed_time_exp = int(config['trading'].get('bypass_elapsed_time_exp', DEFAULT_BYPASS_ELAPSED_TIME_EXP))
        self.elapsed_time_exp = int(config['trading'].get('elapsed_time_exp', DEFAULT_ELAPSED_TIME_EXP))

    def __repr__(self):
        return f"BotRunner - {self.run_forever}"
            
    def buffer(self) -> None:
        sleep_time = random.uniform(self.sleep_buffer_min, self.sleep_buffer_max)
        self.logger.debug(f"sleep .. {sleep_time}")
        time.sleep(sleep_time)

    def backoff(self) -> None:
        sleep_time = self.back_off_start_count + (self.back_off_start_count * BACK_OFF_MULTIPLIER)
        self.logger.debug(f"[backoff] sleep .. {sleep_time}")
        time.sleep(sleep_time)
        self.back_off_start_count += sleep_time
        if self.back_off_start_count >= BACK_OFF_LIMIT:
            self.back_off_start_count = BACK_OFF_START_COUNT


    def run(self, args):

        while True:
            try:
                if self.trade_type == "spot":
                    self.run_spot()                
                else:
                    self.logger.info("Nothing to run.. ")
                    self.buffer()
            except Exception as exc:
                if not self.run_forever:
                    break
                self.logger.warning(f"Error running bot.. - {exc}")
                self.logger.info(traceback.format_exc())
                self.backoff()

    def run_spot(self):

        # check lotsize
        if not self.bot.is_allowed_lotsize(trading_pair=self.trading_pair, amount=self.amount):
            self.logger.info(f"Stopping bot..")
            self.buffer()
            return            

        # show account
        self.bot.show_account()
        transactionId = 0

        while True:
        
            # get predictions
            predictions = self.bot.get_predictions(symbol=self.symbol)
            if not predictions:
                self.logger.info(f"no scraped predictions yet for {self.trading_pair} in pred_table")
                self.buffer()
                continue

            try:
                if int(predictions[0]['elapsed_time(min)']) <= self.buy_delay:
                    self.logger.info(f"prediction is still less < {self.buy_delay} min(s) for {self.trading_pair} in pred_table")
                    self.buffer()
                    continue
            except:
                if predictions[0]['position'] == 'none' and predictions[0]['elapsed_time(min)'] == "-":
                    self.logger.info(f"skipping .. {self.trading_pair} - no predictions yet ..")
                    self.buffer()
                    continue

            # get open orders and get highest bid
            bid_price = self.bot.get_order_book(amount=self.amount, symbol=self.trading_pair, position_type="bid")

            # check if notonial size is okay
            if not self.bot.is_allowed_notional_size(
                    trading_pair=self.trading_pair, amount=self.amount, price=bid_price
                ):
                self.buffer()
                continue

            # place "bid" order
            order = self.bot.set_order(
                symbol=self.trading_pair, side="BUY", stype="LIMIT", 
                quantity=self.amount, price=bid_price, timeInForce="GTC"
            )

            # generated transaction id
            result = self.bot.save_requested_position({
                "transactionId": transactionId,
                "symbol": self.trading_pair,
                "tradingType": self.trade_type,
                "side": "BUY",
                "amount": self.amount,
                "orderId": order["orderId"],
                "status": order["status"],
                "buyPrice": bid_price,
                "origBuyQty": float(order["origQty"]),
                "executedBuyQty": float(order["executedQty"]),
                "cummulativeBuyQuoteQty": float(order["cummulativeQuoteQty"])
            })

            transactionId = result["id"]
            orderId = order["orderId"]
            self.logger.info(f"[start] new transactionId: {transactionId}")

            buyUpdateData = {
                "transactionId": transactionId,
                "orderId": orderId,
                "status": order["status"]
            }

            bid_status = False            
            for _ in range(self.bid_retry):

                self.buffer()

                details = self.bot.get_order_details(symbol=self.trading_pair, orderId=orderId)               
                status = details["status"]

                buyUpdateData["status"] = status
                buyUpdateData["origBuyQty"] = float(details['executedQty'])
                buyUpdateData["executedBuyQty"] = float(details['origQty'])
                buyUpdateData["cummulativeBuyQuoteQty"] = float(details['cummulativeQuoteQty'])
                
                if status != "FILLED":
                    self.logger.info(f"[{_}][bid] waiting order to be filled ..")
                    self.bot.render_tbl(
                        result=[{
                            "trading_pair": self.trading_pair, "bid": bid_price, "status": status
                        }], field_names=[
                            "trading_pair", "bid", "status", "executedBuyQty", "origBuyQty", "percentage"
                        ]
                    )
                    self.bot.save_requested_position(buyUpdateData)
                
                if status == "PARTIALLY_FILLED":
                    self.logger.info(f"[{_}][bid] order partially filled ..")                    
                    # update actual buy quantity
                    buyUpdateData["buyPrice"] = float(details['price'])
                    buyUpdateData["actualBuyQty"] = float(details['cummulativeQuoteQty']) / float(details['price'])
                    self.bot.save_requested_position(buyUpdateData, render=True)

                if status == "FILLED":
                    self.logger.info(f"[{_}][bid] order filled ..")
                    bid_status = True                   
                    # update actual buy quantity
                    buyUpdateData["buyPrice"] = float(details['price'])
                    buyUpdateData["actualBuyQty"] = float(details['cummulativeQuoteQty']) / float(details['price'])
                    self.bot.save_requested_position(buyUpdateData, render=True)
                    break

            # skip next steps if bid is unsuccessful
            if bid_status == False:
                self.logger.info(f"cancelling orderId: {orderId} @ bid: {bid_price}")
                result = self.bot.cancel_order(symbol=self.trading_pair, orderId=orderId)
                buyUpdateData['status'] = result['status']
                self.bot.save_requested_position(buyUpdateData)
                continue
            
            # buy check point
            self.bot.show_account(symbol=self.symbol)
            self.logger.info(f"[{_}][buy] transaction summary")
            self.bot.render_tbl(result=[{
                    "trading_pair": self.trading_pair, 
                    "quantity": details['executedQty'], 
                    "bid_price": bid_price,
                    "total_amount": float(bid_price) * float( buyUpdateData["executedBuyQty"])
                }],  
                field_names=["trading_pair", "quantity", "bid_price", "total_amount"]
            )

            # wait for selling
            sell_signal = False
            while True:

                # get predictions
                predictions = self.bot.get_predictions(symbol=self.symbol)

                # calculate current price - profit/loss
                profitData = self.bot.get_profit(transactionId=transactionId, bid_price=bid_price)
                profitData['transactionId'] = transactionId
                profitData['status'] = status

                # if position is `none` bot will force close the position
                sell_signal = True if predictions[0]['position'] == 'none' else False
                # get current elapsed_time
                elapsed_time = float(predictions[0]['elapsed_time(min)'])
                
                if float(elapsed_time) >= float(self.elapsed_time_exp):
                    sell_signal = True
                    self.logger.info(f"[sell_signal] reached elapsed_time force sell: {self.trading_pair} position")
                else:
                    self.logger.info(f"[sell_signal] waiting for sell signal for {self.trading_pair}")
                    self.logger.info(f"[sell_signal] sell(?):{'Yes' if sell_signal else 'No'}")
                    self.logger.info("[sell_signal] unrealized profit: {unrealizedProfit}".format(**profitData))

                self.bot.save_requested_position(profitData)

                if sell_signal:
                    break

                self.buffer()

            sellUpdateData = {
                "transactionId": transactionId,
                "orderId": orderId
            }
            
            sell_index = self.sell_index
            while sell_signal:

                self.buffer()
                if sell_index > 0:
                    sell_index -= 1
                
                # get the actual executed buy quantity aka "SELL" amount
                sell_data = self.bot.get_order_status(transactionId=transactionId)
                sell_amount = float(sell_data['abq'])

                # get open orders and get highest bid
                sell_price = self.bot.get_order_book(
                    amount=sell_amount, symbol=self.trading_pair, position_type="ask", index=sell_index
                )

                # check if notonial size is okay
                if not self.bot.is_allowed_notional_size(
                    trading_pair=self.trading_pair, amount=sell_amount, price=sell_price
                ):
                    continue

                # place "ask" order
                sell_order = self.bot.close_order(
                    symbol=self.trading_pair, side="SELL", stype="LIMIT", 
                    quantity=sell_amount, price=sell_price
                )
                if not sell_order:
                    continue
                
                sellId = sell_order["orderId"]
                status = sell_order["status"]
                sellUpdateData["side"] = "SELL"
                sellUpdateData["status"] = status
                sellUpdateData["sellId"] = sellId
                sellUpdateData["sellPrice"] = sell_price

                for _ in range(self.sell_retry):

                    self.buffer()
                    details = self.bot.get_order_details(symbol=self.trading_pair, orderId=sellId)
                    status = details["status"]

                    # calculate current price - profit/loss
                    profitData = self.bot.get_profit(transactionId=transactionId, bid_price=bid_price)
                    # update sell data
                    sellUpdateData["status"] = status
                    sellUpdateData["unrealizedProfit"] = profitData['unrealizedProfit']
                    sellUpdateData["origSellQty"] = details["origQty"]
                    sellUpdateData["executedSellQty"] = details["executedQty"]
                    sellUpdateData["cummulativeSellQuoteQty"] = details["cummulativeQuoteQty"]

                    if status != "FILLED":
                        self.logger.info(f"[{_}][sell] waiting order to be filled ..")                        
                        self.bot.save_requested_position(sellUpdateData)
                    
                    if status == "PARTIALLY_FILLED":
                        self.logger.info(f"[{_}][sell] order partially filled ..")                        
                        # update actual sell quantity
                        sellUpdateData["sellPrice"] = float(details['price'])
                        sellUpdateData["actualSellQty"] = float(float(details['cummulativeQuoteQty']) / float(details['price']))
                        self.bot.save_requested_position(sellUpdateData)

                    if status == "FILLED": break

                # refresh retry to next available sell price iteration
                if status != "FILLED":
                    cancel_order = self.bot.cancel_order(symbol=self.trading_pair, orderId=sellId)
                    sellUpdateData["status"] = cancel_order["status"]                    
                    self.bot.save_requested_position(sellUpdateData)
                    continue

                if status == "FILLED":
                    self.logger.info(f"[{_}][sell] transaction summary")
                    # update actual sell quantity
                    sellUpdateData["sellPrice"] = float(details['price'])
                    sellUpdateData["actualSellQty"] = float(details['cummulativeQuoteQty']) / float(details['price'])
                    # calculate current price - profit/loss
                    profitData = self.bot.get_profit(transactionId=transactionId, bid_price=bid_price, sell_price=sell_price)
                    sellUpdateData["unrealizedProfit"] = profitData['unrealizedProfit']
                    sellUpdateData["realizedProfit"] = profitData['realizedProfit']                 
                    sellUpdateData["isExpired"] = 1
                    sellUpdateData["status"] = "CLOSED"
                    self.logger.info(f"[{_}][sell] transaction saved..")
                    self.bot.save_requested_position(sellUpdateData, render=True)
                    break                

                
            self.bot.show_account(symbol=self.symbol)
            self.buffer()
            if not self.run_forever:
                break
            
            self.logger.info(f"[end] finish transactionId: {transactionId}")
            # create new transaction
            transactionId = 0
                    
if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="tradingbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="python app.py --config=config.ini"
    )
    
    parser.add_argument(
        '--config',
        dest='config',
        type=str,
        help='config path'
    )

    args = parser.parse_args()
    config = configparser.ConfigParser()
    config.read(args.config)

    c = Bot(config=config)
    c.run(args)
