import json
import sys
import configparser
import argparse

from bot import TradingBotClient

def add_position(args) -> None:

    # get recent prediction
    predictions = bot.get_predictions(config['trading']['symbol'])
    pred = predictions[0]
    amount = float(pred['amount']) if not float(bot.amount) else float(bot.amount)
    entry_price = float(pred['entry_price']) if not float(bot.entry_price) else float(bot.entry_price)
    
    if bot.trade_type == "futures":

        # check if there's an existing position
        result = bot.get_position_data(symbol=config['trading']['trading_pair'])
        if result:
            if result['oid']:
                check_order_status(orderId=result['oid'])
            return None

        # check if elapsed time is more than buffer time
        if int(pred['elapsed_time(min)']) <= 3:
            print(f"[add_position] wait for elapsed time to cooldown..")
            return

        result = None
        if pred['position'] == 'short':
            # set order
            result = bot.set_order(
                symbol=bot.trading_pair, side='SELL', type='LIMIT', quantity=amount,
                price=entry_price, timeInForce='GTC'
            )
        elif pred['position'] == 'long':
            # set order
            result = bot.set_order(
                symbol=bot.trading_pair, side='BUY', type='LIMIT', quantity=amount,
                price=entry_price, timeInForce='GTC'
            )
        if result:
            # trade type
            result["trade_type"] = config["settings"]["trade_type"]
            # add targetPrice
            result['targetPrice'] = pred['target_price'] if not float(bot.target_price) else bot.target_price
            orderId = result['orderId']
            bot.save_requested_position(result)
            print(f"[add_position] Order Requested - {json.dumps(result, indent=4)}")
            print(f"[add_position] OrderId: {orderId}")

    elif bot.trade_type == "spot":

        # check if there's an existing position
        result = bot.get_position_data(symbol=config['trading']['trading_pair'], tty=bot.trade_type)
        if result:
            print("there's an existing traded for {symbol} that is not yet filled".format(
                symbol=config['trading']['trading_pair'])
            )
            print(result)
            return
         
        if not result:
            # get order book
            entry_price = bot.get_order_book(symbol=bot.trading_pair, position_type="bid")
            # set order
            result = bot.set_order(
                symbol=bot.trading_pair, side="BUY", stype="LIMIT", 
                quantity=amount, price=entry_price, timeInForce='GTC'
            )
            # save to database
            if result:
                # trade type
                result["trade_type"] = bot.trade_type
                orderId = result['orderId']
                bot.save_requested_position(result)
                print(f"[add_position] Order Requested - {json.dumps(result, indent=4)}")
                print(f"[add_position] OrderId: {orderId}")

def check_order_status(args) -> None:


    if bot.trade_type == "futures":

        orderId = int(args.orderId)
        print(f"[check_order_status] checking status for orderId:{orderId} - pair: {config['trading']['trading_pair']}")
        if orderId:
            result = bot.get_position_data(
                symbol=config['trading']['trading_pair'], orderId=orderId
            )
        else:
            result = bot.get_position_data(symbol=config['trading']['trading_pair'])
            orderId = result['oid']

        predictions = bot.get_predictions(config['trading']['symbol'])
        if result:
            orderId = result['oid']
            details = bot.get_order_details(
                symbol=config['trading']['trading_pair'], timestamp=result['ut'], orderId=orderId
            )
            if details:
                if details['status'] == 'CANCELED':
                    bot.mark_position_cancelled(orderId=orderId)
                else:
                    # get initial position
                    current_position = bot.get_current_position(symbol=details['symbol'])
                    # get current price
                    current_price = bot.get_prices(symbol=details['symbol'])
                    if current_position:
                        details['unrealizedProfit'] = current_position['unrealizedProfit']
                        details['initialMargin'] = current_position['initialMargin']
                        details['roE'] = current_position['roE']
                        details['updateTime'] = current_position['updateTime']
                        details['currentPrice'] = current_price['price']
                    # save data to table: trading_table
                    bot.save_requested_position(details)
                    if details['status'] in ('FILLED', 'PARTIALLY_FILLED'):
                        status = details['status'].lower()
                        if not result['up']:
                            print(f"[check_order_status] order {status} : {json.dumps(details, indent=4)}")
                        else:
                            print(f"[check_order_status] unrealizedProfit: {result['up']}")
                    else:
                        print(f"[check_order_status] order:{orderId} still pending..")
                        # check if we need to cancel the order
                        # if position is `none` bot will force close the position
                        is_closed = True if predictions[0]['position'] == 'none' else False
                        # if elapsed_time >= 60
                        elapsed_time = predictions[0]['elapsed_time(min)']
                        if is_closed or (elapsed_time >= 60):
                            response = bot.cancel_order(symbol=result['s'])
                            print(f"[check_order_status] response - {response}")
                            bot.mark_position_cancelled(orderId=orderId)
            else:
                bot.expire_requested_position(orderId=orderId)
                print(f"[check_order_status] OrderId: {orderId} request is expired.")

    elif bot.trade_type == "spot":
        
        result = bot.get_position_data(symbol=config['trading']['trading_pair'], tty=bot.trade_type)
        orderId = result['oid']

        predictions = bot.get_predictions(config['trading']['symbol'])
        if result:
            orderId = result['oid']
            details = bot.get_order_details(
                symbol=config['trading']['trading_pair'], orderId=orderId
            )
            if details:
                if details['status'] == 'CANCELED':
                    bot.mark_position_cancelled(orderId=orderId)
                else:
                    # get current price
                    current_position = bot.get_prices(symbol=details['symbol'])
                    if current_position:
                        details['updateTime'] = details['updateTime']
                        details['currentPrice'] = current_position['price']
                        unrealizedProfit = float(float(current_position['price']) - float(details['price'])) * float(result['a'])
                        details['unrealizedProfit'] = unrealizedProfit
                    # save data to table: trading_table
                    bot.save_requested_position(details)
                    if details['status'] in ('FILLED', 'PARTIALLY_FILLED'):
                        status = details['status'].lower()
                        print(f"[check_order_status] order {status} : {json.dumps(details, indent=4)}")
                    else:
                        print(f"[check_order_status] order:{orderId} still pending..")
                        # check if we need to cancel the order
                        # if position is `none` bot will force close the position
                        is_closed = True if predictions[0]['position'] == 'none' else False
                        # if elapsed_time >= 60 bot will force close the position
                        elapsed_time = predictions[0]['elapsed_time(min)']
                        if is_closed or (elapsed_time >= 60):
                            response = bot.cancel_order(symbol=result['s'])
                            print(f"[check_order_status] response - {response}")
                            bot.mark_position_cancelled(orderId=orderId)
            else:
                bot.expire_requested_position(orderId=orderId)
                print(f"[check_order_status] OrderId: {orderId} request is expired.")

def close_order(args) -> None:

    if bot.trade_type == "futures":
        orderId = int(args.orderId)
        if orderId:
            result = bot.get_position_data(
                symbol=config['trading']['trading_pair'], orderId=orderId
            )
        else:
            result = bot.get_position_data(symbol=config['trading']['trading_pair'])

        if not result:
            print(f"[close_order] no position for {config['trading']['trading_pair']} pair at the moment..")
            return 

        orderId = result['oid']
        predictions = bot.get_predictions(config['trading']['symbol'])

        if result and predictions:
            # position status
            status = result['st']
            # if position is `none` bot will force close the position
            is_closed = True if predictions[0]['position'] == 'none' else False
            # if elapsed_time >= 60
            elapsed_time = predictions[0]['elapsed_time(min)']
            # check position
            position = ''
            if result['si'] == 'SELL':
                position = 'SHORT'
            elif result['si'] == 'BUY':
                position = 'LONG'

            print(f"[close_order] status: {status}")
            print(f"[close_order] position: {position}")
            print(f"[close_order] close deal:{'Yes' if is_closed else 'No'}")
            print(f"[close_order] elapsed_time: ({elapsed_time}min >= 60min) = {elapsed_time>=60}")

            pos_risk = bot.get_current_position(symbol=config['trading']['trading_pair'])
            current_price = bot.get_prices(symbol=config['trading']['trading_pair'])

            icp = float(current_price['price'])
            itp = float(result['tp'])

            if result['si'] == 'SELL' and (result['st'] in ('FILLED', 'PARTIALLY_FILLED')):
                print(f"[close_order] [tp]({itp}) >= [cp]({icp}) = {itp >= icp}")
                if (itp >= icp) or is_closed or (elapsed_time >= 60) or 1:
                    print(f"[close_order] - {json.dumps(result, indent=4)}")
                    result = bot.close_order(
                        symbol=config['trading']['trading_pair'], side="SELL", type="MARKET",
                        quantity=float(result['a']), reduceOnly='true'
                    )
                    print(f"[close_order] - marking position closed for orderId:{orderId}")
                    bot.mark_position_closed(orderId=orderId)

            elif result['si'] == 'BUY' and (result['st'] in ('FILLED', 'PARTIALLY_FILLED')):
                print(f"[close_order] [tp]({itp}) <= [cp]({icp}) = {itp <= icp}")
                if (itp <= icp) or is_closed or (elapsed_time >= 60):
                    print(f"[close_order] - {json.dumps(result, indent=4)}")
                    result = bot.close_order(
                        symbol=config['trading']['trading_pair'], side="BUY", type="MARKET", 
                        quantity=float(result['a']), reduceOnly='true'
                    )
                    print(f"[close_order] - marking position closed for orderId:{orderId}")
                    bot.mark_position_closed(orderId=orderId)

            if pos_risk:
                print(f"[close_order] initialMargin: {pos_risk['initialMargin']}")
                print(f"[close_order] unrealizedProfit: {pos_risk['unrealizedProfit']}")
                print(f"[close_order] ROE: {pos_risk['roE']}")
                
    elif bot.trade_type == "spot":
        
        symbol = config['trading']['symbol']
        trading_pair = config['trading']['trading_pair']
        result = bot.get_position_data(symbol=trading_pair, tty=bot.trade_type)
        if not result:
            print(f"[close_order] no position for {trading_pair} pair at the moment..")
            return

        orderId = result['oid']
        sellId = result['sid']

        predictions = bot.get_predictions(symbol=symbol)
        if result and predictions:

            # position status
            status = result['st']
            # if position is `none` bot will force close the position
            is_closed = True if predictions[0]['position'] == 'none' else False
            # if elapsed_time >= 60
            elapsed_time = predictions[0]['elapsed_time(min)']

            print(f"[close_order] status: {status}")
            print(f"[close_order] close deal:{'Yes' if is_closed else 'No'}")
            print(f"[close_order] elapsed_time: ({elapsed_time}min >= 60min) = {elapsed_time>=60}")

            if sellId and status != "FILLED":
                # result = bot.cancel_order(symbol=trading_pair, orderId=sellId)
                sellId = None

            # if status in ('FILLED', ) and not sellId:
            if is_closed or (elapsed_time >= 60) and not sellId or 1:
                # get sell order book
                sell_price = bot.get_order_book(symbol=trading_pair, position_type="ask")
                sell_order = bot.close_order(
                    symbol=trading_pair, side="SELL", type="LIMIT", 
                    quantity=float(result['a']), price=float(sell_price), reduceOnly='true'
                )
                if result and sell_order:
                    current_price = bot.get_prices(symbol=trading_pair)
                    # trade type
                    result['status'] = sell_order['status']
                    result['side'] = sell_order['side']
                    result['orderId'] = orderId
                    result['sellId'] = sell_order['orderId']
                    result['currentPrice'] = current_price['price']
                    result['price'] = float(sell_price)
                    unrealizedProfit = float(float(current_price['price']) - float(sell_price)) * float(result['a'])
                    result['unrealizedProfit'] = unrealizedProfit
                    print(f"[close_order] - order: {json.dumps(result, indent=4)}") 
                    bot.save_requested_position(result)
                    orderId = result['orderId']
                    sellId = sell_order['orderId']
                    print(f"[add_position] Order Requested - {json.dumps(result, indent=4)}")
                    print(f"[add_position] OrderId: {orderId} - SellId: {sellId}")
                    print(f"[add_position] unrealizedProfit: {unrealizedProfit}")

if __name__ == "__main__":

    option = None
    orderId = None

    parser = argparse.ArgumentParser(
        description="tradingbot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="python app.py --option order"
    )
    parser.add_argument(
        '--option',
        dest='option',
        type=str,
        choices=['order', 'check_order', 'close_order'],
        help='trade option order|check_order|close_order'
    )
    parser.add_argument(
        '--order_id',
        dest='order_id',
        type=str,
        help='order_id returned from adding calling order'
    )

    parser.add_argument(
        '--config',
        dest='config',
        type=str,
        help='config path'
    )

    parser.add_argument(
        '--trade_type',
        dest='trade_type',
        type=str,
        help='trading type'
    )

    args = parser.parse_args()

    config_path = "/opt/config.ini"
    if args.config:
        config_path = args.config

    config = configparser.ConfigParser()
    config.read(config_path)

    bot = TradingBotClient(**config)
    if args.option == "order":
        add_position(args)
    elif args.option == "check_order":
        check_order_status(args)
    elif args.option == "close_order":
        close_order(args)