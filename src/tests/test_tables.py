#!/bin/usr/python3

import sys
import sqlite3
from prettytable import from_db_cursor

sqldb = None
query = None
try:
    sqldb = sys.argv[1]
    query = sys.argv[2]
except Exception as exc:
    print(f"No sqldb .. {exc}")

if sqldb and query:
    connection = sqlite3.connect(sqldb)
    cursor = connection.cursor()
    q = query.lower().split(" ")
    if q[0] == "select":
        cursor.execute(query)
        tbl = from_db_cursor(cursor)
        print(tbl)
    else:
        cursor.execute(query)
        connection.commit()
        tbl = from_db_cursor(cursor)
        last_id = cursor.lastrowid
        print("Done")

    connection.close()













