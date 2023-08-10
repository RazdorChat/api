from __future__ import annotations

import secrets
from random import randint
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db import DBConnection
    from redis import Redis


def generate_user_id(db_conn: DBConnection) -> int:
    """Generates a user ID.

    Args:
        db_conn (DBConnection): The database connection to use.

    Returns:
        int: The generated user ID.
    """
    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM users WHERE id=?", _id)
        if not check:
            return _id


def generate_user_discrim(db_conn: DBConnection, username: str) -> int:
    """Generates a discriminator for a user.

    Args:
        db_conn (DBConnection): The database connection to use.
        username (str): The username to generate a discriminator for.

    Returns:
        int: The generated discriminator.
    """
    check = db_conn.query("SELECT discrim FROM users WHERE _name = ?", username)
    if len(check) == 9999:  # The username has hit its limit for discriminators
        _max = int(f"{str(len(check))}9")  # Up the character limit +1
    elif check != None and len(check) != 0:  # There are available discrims
        _discrims = [int(x) for x in check]
        _max = max(_discrims)
    elif check == None or len(check) == 0:  # Nobody has used the username before, start out on the minimum for 4 char discrims
        _max = 9999  # Max combinations for 4 character discriminators
    while 1:
        _discrim = randint(1000, _max)  # Minimum of 4 char discrims
        if _discrim == 1000:
            _discrim = "0001"  # Congrats, you got a really rare discrim :)
        if _discrim not in db_conn.query("SELECT _name FROM users WHERE discrim = ?", _discrim):  # username + discrim combo isnt taken
            return _discrim


def generate_message_id(db_conn: DBConnection) -> int:
    """Generates a message ID.

    Args:
        db_conn (DBConnection): The database connection to use.

    Returns:
        int: The generated message ID.
    """

    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM messages WHERE id=?", _id)
        if not check:
            return _id


def generate_dm_id(db_conn: DBConnection) -> int:
    """Generates a DM ID.

    Args:
        db_conn (DBConnection): The database connection to use.

    Returns:
        int: The generated DM ID.
    """

    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM DMs WHERE id=?", _id)
        if not check:
            return _id


def generate_session_token(redis_conn: Redis, author_id: int | str) -> str:
    """Generates a session token.

    Args:
        redis_conn (object): Redis connection object
        author_id (int | str): The ID of the author.

    Returns:
        str: The generated session token.

    """
    token = redis_conn.get(author_id)
    if not token:
        token = secrets.token_urlsafe(32)
        redis_conn.set(author_id, token)
    return token


def get_session_token(redis_conn: Redis, author_id: int | str) -> str:
    """Gets a session token.

    Args:
        redis_conn (object): Redis connection object
        author_id (int | str): The ID of the author.

    Returns:
        str: The session token.
    """
    data = redis_conn.get(author_id)
    if not data:
        return "fake_data_none"  # what
    return data
