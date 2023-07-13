import os
import sqlite3
import traceback

class SQLiteDB:

    def __init__(self, db):

        self.dbname = db
        self.db = self.connect()
       
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

    def purge_tables(self) -> None:
        return NotImplemented

    def insert(self, sql) -> None:
        try:
            cur = self.db.cursor()
            cur.execute(sql)
            self.db.commit()
        except:
            print(f'[err] - {traceback.format_exc()}')

    def select(self, sql) -> dict:
        try:
            self.db.row_factory = self.dict_factory
            cur = self.db.cursor()
            cur.execute(sql)
            return cur.fetchall()
        except:
            print(f'[err] - {traceback.format_exc()}')
            
    def select_one(self, sql) -> dict:
        try:
            self.db.row_factory = self.dict_factory
            cur = self.db.cursor()
            cur.execute(sql)
            return cur.fetchone()
        except:
            print(f'[err] - {traceback.format_exc()}')
