from dataclasses import dataclass
import json
from typing import Sequence
import mariadb
import re
from models.dbconfig import DBConfig

DB_CONFIG_PATH = 'server_data/db.json' # TODO: replace db.json with a more general config.json format



def mariadb_pool(pool_id: int) -> mariadb.ConnectionPool:
  f = json.load(open(DB_CONFIG_PATH))
  config = DBConfig(
    user=f['user'],
    password=f['password'],
    database=f['database'])
  # Set optional config values
  def set_opt(key: str, t: type):
    if key in f and type(f[key]) is t:
      config[key] = f[key]
  set_opt('host', str)
  set_opt('port', int)
  set_opt('pool_size', int)

  return mariadb.ConnectionPool(
    host=config.host,
    port=config.port,
    database=config.database,

    user=config.user,
    password=config.password,

    pool_size=config.pool_size,
    pool_name=f'pool_{config.database}{pool_id}')

class DBConnection:
  conn: mariadb.Connection
  cur: mariadb.Cursor
  autoclose = False

  def __init__(self, pool: mariadb.ConnectionPool, autoclose: bool|None):
    self.conn = pool.get_connection()
    self.cur = self.conn.cursor(
      dictionary=True)
    if autoclose is not None:
      self.autoclose = autoclose

  # Omit the column name for single column queries
  @staticmethod
  def map_col(query) -> str|None:
    map_col: str = None
    re_result = re.search('^select (\w+) from', query, flags=re.IGNORECASE)
    if re_result is not None and len(re_result.groups()) > 0:
      map_col = re_result.groups()[0]
    return map_col

  def query_row(self, query: str, *args) -> dict|str:
    self.cur.execute(query, args)
    result = self.cur.fetchone()
    map_col = self.map_col(query)
    if result is not None and map_col is not None:
      result = result[map_col]
    if self.autoclose:
      self.conn.close()
    return result
  
  def query(self, query: str, *args) -> list[dict]:
    self.cur.execute(query, args)
    result = list()
    for row in self.cur:
      map_col = self.map_col(query)
      if row is not None and map_col is not None:
        row = row[map_col]
      result.append(row)
    if self.autoclose:
      self.conn.close()
    return result

  def execute(self, stmt: str, *args) -> None:
    self.cur.execute(stmt, args)
    if self.autoclose:
      self.conn.close()

  def begin(self) -> None:
    self.conn.begin()
  def rollback(self) -> None:
    self.conn.rollback()
    self.conn.close()
  def commit(self) -> None: # Closes the connection
    self.conn.commit()
    self.conn.close()

class DB:
  pool: mariadb.ConnectionPool
  def __init__(self, pool: mariadb.ConnectionPool):
    self.pool = pool

  def query_row(self, query: str, *args) -> dict:
    return DBConnection(self.pool, True).query_row(query, *args)

  def query(self, query: str, *args) -> list[dict]:
    return DBConnection(self.pool, True).query(query, *args)

  def execute(self, stmt: str, *args) -> None:
    conn = DBConnection(self.pool, False)
    conn.execute(stmt, *args)
    conn.commit()

  def begin(self) -> DBConnection:
    conn = DBConnection(self.pool, False)
    conn.begin()
    return conn
