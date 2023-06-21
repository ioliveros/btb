#!/bin/bash

create_db(){
   rm -rf $DATABASE_NAME
   echo "creating database .."
   sqlite3 -batch $DATABASE_NAME ".schema"
}

create_tables(){
   echo "creating tables .."
   sqlite3 -batch $DATABASE_NAME "CREATE TABLE IF NOT EXISTS pred_table (
      id INTEGER PRIMARY KEY,
      c TEXT,
      p TEXT,
      tt INTEGER,
      et INTEGER,
      ep FLOAT,
      tp FLOAT,
      cp FLOAT,
      ps FLOAT,
      a FLOAT,
      cpr FLOAT,
      dp FLOAT,
      mp FLOAT,
      ia INTEGER
   );"
   sqlite3 -batch $DATABASE_NAME "CREATE TABLE IF NOT EXISTS trading_table(
      id INTEGER PRIMARY KEY,
      oid INTEGER,
      sid INTEGER,
      s TEXT,
      si TEXT,
      st TEXT,
      a FLOAT,      
      abq FLOAT,
      cp FLOAT,
      bp FLOAT,
      obq FLOAT,
      ebq FLOAT,
      cbqq FLOAT,
      sp FLOAT,
      asq FLOAT,
      osq FLOAT,
      esq FLOAT,
      csqq FLOAT,
      up FLOAT,
      rp FLOAT,
      ut INTEGER,
      ia INTEGER,
      ie INTEGER,
      tty TEXT
   );"
   sqlite3 -batch $DATABASE_NAME ".tables"
   sqlite3 -batch $DATABASE_NAME ".schema"
}


drop_tables(){
   echo "dropping tables .."
   sqlite3 -batch $DATABASE_NAME "DROP TABLE pred_table;"
}

if [[ "$1" = "create_db" ]]
then
		create_db
elif [[ "$1" = "create_table" ]]
then
		create_table
elif [[ "$1" = "test" ]]
then
		create_db
		create_tables
elif [[ "$1" = "drop_tables" ]]
then
		drop_tables
fi


create_db
create_tables
#drop_tables
