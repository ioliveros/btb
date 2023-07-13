class BaseTable:
 
    def __init__(self) -> None:
        self.feed_source = 'https://crypto-price-prediction.com/prediction_data/pred_table.csv'

    def deserialize(self, data):

        if type(data) is not list:
            data = [data]

        results = []
        for kdata in data:
            results.append({self.dmapper[k]:kdata[k] for k in kdata})
        return results    

class PredTable(BaseTable):

    def __init__(self):

        self.dmapper = {
            'id': 'id',
            'c': 'crypto',
            'p':'position',
            'tt':'trade_time(utc)',
            'et':'elapsed_time(min)',
            'ep':'entry_price',
            'tp':'target_price',
            'cp':'current_price',
            'ps':'price_spread',
            'a':'amount',
            'cpr':'current_profit',
            'dp':'daily_profit',
            'mp':'monthly_profit',
            'ia': 'inserted_at'
        }

    def get_predictions(self, db:object, symbol:str):
        return db.select_one(
            f"SELECT * FROM pred_table WHERE c = '{symbol}' ORDER BY ia DESC LIMIT 1"
        )

    
class TradingTable(BaseTable):

    def __init__(self, logger, **config):

        self.dmapper = {
            'id': 'transactionId',
            'oid': 'orderId',
            'sid': 'sellId',
            's': 'symbol',
            'si': 'side',
            'st': 'status',
            'a': 'amount',
            'cp': 'currentPrice',
            'bp': 'buyPrice',
            'obq': 'origBuyQty',
            'ebq':'executedBuyQty',
            'cbqq':'cummulativeBuyQuoteQty',
            'sp': 'sellPrice',
            'osq': 'origSellQty',
            'esq':'executedSellQty',
            'csqq':'cummulativeSellQuoteQty',            
            'up': 'unrealizedProfit',
            'ut': 'updateTime',
            'ia': 'inserted_at',
            'ia': 'isExpired',
            'tty': 'tradeType'
        }

        self.logger = logger

    def save_requested_position(self, db:object, data:dict):
        result = db.select_one("SELECT * FROM trading_table WHERE id = {transactionId}".format(**data))
        if result:
            set_query = []
            if data.get("side", None):
                set_query.append(f"si = '{data['side']}'")
            if data.get("status", None):
                set_query.append(f"st = '{data['status']}'")
            if data.get("unrealizedProfit", None):
                set_query.append(f"up = '{data['unrealizedProfit']}'")
            if data.get("updateTime", None):
                set_query.append(f"ut = '{data['updateTime']}'")
            if data.get("currentPrice", None):
                set_query.append(f"cp = '{data['currentPrice']}'")
            if data.get("sellId", None):
                set_query.append(f"sid = '{data['sellId']}'")
            if data.get("origBuyQty", None):
                set_query.append(f"obq = '{data['origBuyQty']}'")
            if data.get("executedBuyQty", None):
                set_query.append(f"ebq = '{data['executedBuyQty']}'")
            if data.get("cummulativeBuyQuoteQty", None):
                set_query.append(f"cbqq = '{data['cummulativeBuyQuoteQty']}'")
            if data.get("entryPrice", None):
                set_query.append(f"sp = '{data['sellPrice']}'")
            if data.get("sellPrice", None):
                set_query.append(f"sp = '{data['sellPrice']}'")
            if data.get("isExpired", None):
                set_query.append(f"ie = '{data['isExpired']}'")
            if data.get("origSellQty", None):
                set_query.append(f"osq = '{data['origSellQty']}'")
            if data.get("executedSellQty", None):
                set_query.append(f"esq = '{data['executedSellQty']}'")
            if data.get("cummulativeSellQuoteQty", None):
                set_query.append(f"csqq = '{data['cummulativeSellQuoteQty']}'")
            if data.get("actualBuyQty", None):
                set_query.append(f"abq = '{data['actualBuyQty']}'")
            if data.get("actualSellQty", None):
                set_query.append(f"asq = '{data['actualSellQty']}'")
            if data.get("realizedProfit", None):
                set_query.append(f"rp = '{data['realizedProfit']}'")

            sql = "UPDATE trading_table SET {set_query} WHERE id = {transactionId}".format(
                set_query=",".join(set_query), transactionId=data['transactionId']
            )
            self.logger.debug(f"[save_requested_position] - {sql}")
            # update trading_table
            db.insert(sql)
        else:
            sql = "INSERT INTO trading_table (oid, s, si, st, a, bp, cp, ut, ia, tty) "
            rows = {}
            for k in self.dmapper:
                row_key = self.dmapper[k]
                if not data.get(row_key, None):
                    rows[k] = ""
                else:
                    rows[k] = data[row_key]
            rows['ia'] = "strftime(\'%s\',\'now\')"
            sql += "VALUES ('{oid}', '{s}', '{si}', '{st}', '{a}', '{bp}', '{cp}', '{ut}', {ia}, '{tty}')".format(**rows)
            self.logger.debug(f"[save_requested_position] - {sql}")
            db.insert(sql)
            # get lastrow insert
            result = db.select_one("SELECT * FROM trading_table WHERE oid = {oid}".format(**rows))
        
        return result

    def get_position_data(self, db:object, symbol:str, tty:str, orderId:int=None):
        if not orderId:
            return db.select_one(
            f"SELECT * FROM trading_table WHERE s = '{symbol}' \
                AND st != 'CLOSED' AND tty = '{tty}' AND ie IS NULL ORDER BY ia DESC LIMIT 1"
            )
        else:
            return db.select_one(
            f"SELECT * FROM trading_table WHERE oid = {orderId} \
                AND tty = '{tty}' AND ie IS NULL ORDER BY ia DESC LIMIT 1"
            )

    def expire_requested_position(self, db:object, transactionId:int):
        return db.insert(f"UPDATE trading_table SET st = 'EXPIRED', ie = 1 WHERE id = {transactionId}")

    def get_current_position_data(seld, db:object, orderId:int=None):
        return db.select_one(
                f"SELECT * FROM trading_table WHERE oid = {orderId} AND ie IS NULL ORDER BY ia DESC LIMIT 1"
            )

    def mark_position_closed(seld, db:object, transactionId:int=None):
        return db.insert(
                f"UPDATE trading_table SET st = 'CLOSED' , ie = 2 WHERE id = {transactionId}"
            )

    def mark_position_cancelled(self, db:object, transactionId:int=None):
        return db.insert(
                f"UPDATE trading_table SET st = 'CANCELED' , ie = 2 WHERE id = {transactionId}"
            )
    
    def get_order_status(self, db:object, transactionId:int):
        return db.select_one(
            f"SELECT * FROM trading_table WHERE id = {transactionId}"
        )
    