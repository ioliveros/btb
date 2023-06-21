import os
import requests
import logging
import sqlite3
import datetime
from prettytable import PrettyTable

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"

class CryptoPricePredictions:
    
    def __init__(self, config: object, db: object):

        self.feed_source = 'https://crypto-price-prediction.com/prediction_data/pred_table.csv'
        self.mapper = {
            'crypto': 'c',
            'position': 'p',
            'trade_time(utc)': 'tt',
            'elapsed_time(min)': 'et',
            'entry_price': 'ep',
            'target_price': 'tp',
            'current_price': 'cp',
            'price_spread': 'ps',
            'amount': 'a',
            'current_profit': 'cpr',
            'daily_profit': 'dp',
            'monthly_profit': 'mp'
        }
        self.db = db
        self.config = config

    def convert_to_epoch(self, timestamp) -> int:
        epoch  = datetime.datetime(1970, 1, 1)
        return int((datetime.datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S') - epoch).total_seconds())

    def is_exist(self, crypto: str) -> bool:
        r = self.db.select_one(f"SELECT count(*) as count  FROM pred_table WHERE c = '{crypto}'")
        return True if r['count'] else False

    def transform(self, raw_data: list) -> None:
      
        insert_rows = []
        update_rows = []        
        for item in raw_data:
            # map fields
            mapped_data = {self.mapper[k]: item[k] for k in item}
            # normalize mapping with no values
            for _ in self.mapper:
                k = self.mapper[_]
                if not mapped_data.get(k, None):
                    mapped_data[k] = ''
                elif _ == 'trade_time(utc)':
                    mapped_data[k] = self.convert_to_epoch(mapped_data[k])
            
            mapped_data['ia'] = "strftime(\'%s\',\'now\')"
            # check if crypto already exists
            is_exist = self.is_exist(item["crypto"])
            if is_exist:
                sql = "UPDATE pred_table SET "
                sql += "p='{p}', tt='{tt}', et={et}, ep={ep}, ".format(**mapped_data)
                sql += "tp={tp}, cp={cp}, ps={ps}, a={a}, ".format(**mapped_data)
                sql += "cpr={cpr}, dp={dp}, mp={mp}, ia={ia} ".format(**mapped_data)
                sql += "WHERE c = '{c}'".format(**mapped_data)
                update_rows.append(sql)
            else:
                insert_rows.append("('{c}', '{p}', '{tt}', {et}, {ep}, {tp}, {cp}, {ps}, {a}, {cpr}, {dp}, {mp}, {ia})".format(**mapped_data))

        if update_rows:
            for sql in update_rows:
                # print(f"[transform] - update => {sql}")
                self.db.insert(sql)

        if insert_rows:
            sql = "INSERT INTO pred_table (c, p, tt, et, ep, tp, "
            sql += "cp, ps, a, cpr, dp, mp, ia) VALUES "
            sql += ", ".join(insert_rows)
            # print(f"[transform] - insert new => {sql}")
            self.db.insert(sql)

    def download(self, feed_source:str=None) -> None:

        url = self.feed_source
        if feed_source:
            url = feed_source

        # request url
        with requests.Session() as s:
            response = s.get(url, headers={"user-agent": USER_AGENT, "content-type": "application/json"})

        data = []
        if response.status_code == 200:
            items = [item.strip('\r') for item in response.content.decode().split('\n') if item]
            supported_columns = [col.lower() for col in items[0].split(',') if col]
            for row in items[1:]:
                if not row: continue
                item = {}
                for i, d in enumerate(row.split(",")):
                    if not d: continue
                    item[supported_columns[i]] = d.strip().lower()
                data.append(item)

        # print tables
        tbl = PrettyTable()
        tbl.field_names = [f for f in self.mapper]
        for row in data:
            row_vals = []
            if row['crypto'] != self.config['trading']['symbol']: continue
            for k in self.mapper:
                if not row.get(k, None):
                    row_vals.append('-')
                else:
                    row_vals.append(row[k])
            tbl.add_row(row_vals)
        print(f'[download] .. ')
        print(tbl)
        return data


if __name__ == "__main__":
    feed = CryptoPricePredictions()
    data = feed.download()
    feed.transform(data)
