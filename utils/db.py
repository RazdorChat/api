from __future__ import annotations

import json
import re

import mariadb

from models.dbconfig import DBConfig

DB_CONFIG_PATH = "server_data/db.json"  # TODO: replace db.json with a more general config.json format


def mariadb_pool(pool_id: int) -> mariadb.ConnectionPool:
    """Creates a mariadb connection pool from a config file.

    Args:
        pool_id (int): The ID of the pool, used for logging.

    Returns:
        mariadb.ConnectionPool: The connection pool.
    """

    f = json.load(open(DB_CONFIG_PATH))
    config = DBConfig(user=f["user"], password=f["password"], database=f["database"])

    # Set optional config values
    def set_opt(key: str, t: type):
        if key in f and type(f[key]) is t:
            config[key] = f[key]

    set_opt("host", str)
    set_opt("port", int)
    set_opt("pool_size", int)

    return mariadb.ConnectionPool(
        host=config.host,
        port=config.port,
        database=config.database,
        user=config.user,
        password=config.password,
        pool_size=config.pool_size,
        pool_name=f"pool_{config.database}{pool_id}",
    )


class DBConnection:
    """Wrapper for a DB connection, with some helper functions.

    Args:
        pool (mariadb.ConnectionPool): The connection pool to use.
        autoclose (bool | None): Whether to close the connection after a query. Defaults to False.
    """

    conn: mariadb.Connection
    cur: mariadb.Cursor
    autoclose = False

    def __init__(self, pool: mariadb.ConnectionPool, autoclose: bool | None):
        self.conn = pool.get_connection()
        self.cur = self.conn.cursor(dictionary=True)
        if autoclose is not None:
            self.autoclose = autoclose

    # Omit the column name for single column queries
    @staticmethod
    def map_col(query: str) -> str | None:
        """Maps the column name to the result of a query.

        Args:
            query (str): The query to map the column name from.
        """
        map_col: str = None
        re_result = re.search("^select (\w+) from", query, flags=re.IGNORECASE)
        if re_result is not None and len(re_result.groups()) > 0:
            map_col = re_result.groups()[0]
        return map_col

    def query_row(self, query: str, *args) -> dict | str:
        """Queries the DB for a single row.

        Args:
            query (str): The query to execute.
            args: The arguments to pass to the query.

        Returns:
            dict | str: The result of the query.

        """
        self.cur.execute(query, args)
        result = self.cur.fetchone()
        map_col = self.map_col(query)
        if result is not None and map_col is not None:
            result = result[map_col]
        if self.autoclose:
            self.conn.close()
        return result

    def query(self, query: str, *args) -> list[dict]:
        """Queries the DB for multiple rows.

        Args:
            query (str): The query to execute.
            args: The arguments to pass to the query.

        Returns:
            list[dict]: The result of the query.
        """
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
        """Executes a statement.

        Args:
            stmt (str): The statement to execute.
            args: The arguments to pass to the statement.
        """
        self.cur.execute(stmt, args)
        if self.autoclose:
            self.conn.close()

    def begin(self) -> None:
        """Begins a transaction."""
        self.conn.begin()

    def rollback(self) -> None:
        """Rolls back a transaction."""
        self.conn.rollback()
        self.conn.close()

    def commit(self) -> None:
        """Commits a transaction and closes the connection."""
        self.conn.commit()
        self.conn.close()


class DB:
    """Wrapper for a DB connection pool, with some helper functions.

    Args:
        pool (mariadb.ConnectionPool): The connection pool to use.
    """

    pool: mariadb.ConnectionPool

    def __init__(self, pool: mariadb.ConnectionPool):
        self.pool = pool

    def query_row(self, query: str, *args) -> dict:
        """Queries the DB for a single row.

        Args:
            query (str): The query to execute.
            args: The arguments to pass to the query.

        Returns:
            dict: The result of the query.
        """
        return DBConnection(self.pool, True).query_row(query, *args)

    def query(self, query: str, *args) -> list[dict]:
        """Queries the DB for multiple rows.

        Args:
            query (str): The query to execute.
            args: The arguments to pass to the query.

        Returns:
            list[dict]: The result of the query.
        """
        return DBConnection(self.pool, True).query(query, *args)

    def execute(self, stmt: str, *args) -> None:
        """Executes a statement.

        Args:
            stmt (str): The statement to execute.
            args: The arguments to pass to the statement.
        """
        conn = DBConnection(self.pool, False)
        conn.execute(stmt, *args)
        conn.commit()

    def begin(self) -> DBConnection:
        """Begins a transaction.

        Returns:
            DBConnection: The connection to used for the transaction.
        """
        conn = DBConnection(self.pool, False)
        conn.begin()
        return conn
