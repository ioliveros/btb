import os
import sqlite3
import traceback
import time


MAX_RETRY_COUNT = 5

class SQLiteDB:

    def __init__(self, db):
        self.dbname = db
        self.db = self.connect()
        self.retry_count = 1        

    def __del__(self):
        self.db.close()

    def dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def connect(self) -> object:
        db = sqlite3.connect(self.dbname)
        return db

    def reconnect(self) -> object:
        self.db.close()
        self.db = self.connect()
        self.retry_count = 1

    def purge_tables(self) -> None:
        return NotImplemented

    def execute_sql_with_retry(self, sql, commit=False, fetch_one=False) -> object:
        while True:
            try:
                if commit:
                    cur = self.db.cursor()
                    cur.execute(sql)
                    self.db.commit()
                    return
                else:
                    self.db.row_factory = self.dict_factory
                    cur = self.db.cursor()
                    cur.execute(sql)
                    if fetch_one:                       
                        return cur.fetchone()
                    else:
                        return cur.fetchall()
            except sqlite3.Error:
                print(f"Database connection error. Retrying... sleep::{self.retry_count}")
                time.sleep(self.retry_count)
                self.retry_count = min(self.retry_count * 2, MAX_RETRY_COUNT)
                self.reconnect()

    def insert(self, sql) -> None:
        self.execute_sql_with_retry(sql, commit=True)

    def select(self, sql) -> dict:
        return self.execute_sql_with_retry(sql)

    def select_one(self, sql) -> dict:
        return self.execute_sql_with_retry(sql, commit=False, fetch_one=True)