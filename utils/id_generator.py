from __future__ import annotations

import secrets
from random import randint
from typing import (
    TYPE_CHECKING, Tuple
)
from utils.redis import RDB
from pottery import Redlock

if TYPE_CHECKING:
    from db import DBConnection
    from redis import Redis

class UserDiscrimLocks:
    prefix_lock: Redlock|None
    discrim_lock: Redlock|None

    def __init__(self):
        self.prefix_lock = None
        self.discrim_lock = None

    def lock_prefix(self, username: str, prefix: str|int) -> bool:
        key = f'username:{username}:discrim_prefix_locks:{prefix}'
        # auto_release_time for prefix_lock should be >= (try_random_passes * 2) * (timeout for discrim_lock.acquire())
        # to minimize the likelihood of a prefix lock expiring before a user account is created
        self.prefix_lock = Redlock(key=key, masters={RDB}, auto_release_time=1)
        return self.prefix_lock.acquire()
    def lock_discrim(self, username: str, prefix: str|int, discrim: str|int) -> bool:
        key = f'username:{username}:discrim_locks:{prefix}:{discrim}'
        self.discrim_lock = Redlock(key=key, masters={RDB}, auto_release_time=1)
        return self.discrim_lock.acquire(timeout=.1)
    def release_all(self):
        if self.discrim_lock is not None:
            self.discrim_lock.release()
        if self.prefix_lock is not None:
            self.prefix_lock.release()


# Determine or generate user discriminator prefix
def _generate_user_discrim_prefix(db_conn, username: str) -> Tuple[int, UserDiscrimLocks]:
    """ Determin or generate user discriminator prefix

    Args:
        db_conn: DB Connection object.
        username (str): User's Username.

    Returns:
        Tuple[int, UserDiscrimLocks]: Discrim prefix and current Locks
    """    
    try_random_passes = 5
    lock_prefix_threshold = 9900 # This threshold may be a bit low
    prefix_count_query = 'SELECT COUNT(discrim) FROM users WHERE _name = ? AND discrim_prefix = ?'
    locks = UserDiscrimLocks()
    # If a 4-digit discrim can be used, return a discrim_prefix of 0 
    count = db_conn.query_row(prefix_count_query, username, 0)
    if count < 10_000 and (count < lock_prefix_threshold or locks.lock_prefix(username, 0)):
        return 0, locks
    # Get prefix from redis if it exists
    redis_key = f'username:{username}:fill_discrim_prefix'
    redis_prefix = RDB.get(redis_key)
    if redis_prefix is not None:
        count = db_conn.query_row(prefix_count_query, username, redis_prefix)
        if count < 10_000 and (count < lock_prefix_threshold or locks.lock_prefix(username, redis_prefix)):
            return int(redis_prefix), locks
    # Generate a new nonzero discrim_prefix
    for _ in range(try_random_passes): # Try to generate a random prefix to avoid leaking username popularity info
        prefix = randint(10, 99)
        count = db_conn.query_row(prefix_count_query, username, prefix)
        if count == 10_000:
            continue
        # Once a discrim prefix is half full, use it exclusively until full
        if count >= 5000:
            RDB.set(redis_key, str(prefix))
        if count < lock_prefix_threshold or locks.lock_prefix(username, prefix):
            return prefix, locks
    # If a random prefix couldn't be chosen, do a sequential sweep to find the lowest prefix available
    # When a prefix is chosen via this method, it will be assigned to fill_discrim_prefix in redis
    for prefix in range(10, 100):
        count = db_conn.query_row(prefix_count_query, username, prefix)
        if count == 10_000:
            continue
        RDB.set(redis_key, str(prefix))
        if count < lock_prefix_threshold or locks.lock_prefix(username, prefix):
            return prefix, locks
    return -1, locks # -1 is returned if a username has no possible discrim prefixes left, and thus no possible discriminators

# Generate a discriminator
# The first int in the tuple returned is the discrim_prefix, the second is the discrim
# If either value is negative, generation has failed 
def generate_user_discrim(db_conn, username: str) -> Tuple[int, int, UserDiscrimLocks]:
    """ Generate a user discriminator.

    Args:
        db_conn: DB Connection object.
        username (str): User's Username.

    Returns:
        Tuple[int, int, UserDiscrimLocks]: Discrim prefix, Discrim, Current Locks.
    """    
    try_random_passes = 5
    # Determine discrim_prefix 
    prefix, locks = _generate_user_discrim_prefix(db_conn, username)
    if prefix == -1:
        # Return -1 to signal that a username is totally saturated (all 900k possible discrims are saturated,
        # which can be determined from all 90 possible discrims being saturated)
        return -1, -1, locks
    discrim_exists_query = 'SELECT EXISTS(SELECT 1 FROM users WHERE _name = ? AND discrim_prefix = ? AND discrim = ?)'
    # Try to randomly generate discrim
    for _ in range(try_random_passes):
        discrim = randint(0, 9999)
        exists = db_conn.query_row(discrim_exists_query, username, prefix, discrim)
        if not exists and locks.lock_discrim(username, prefix, discrim):
            return prefix, discrim, locks
    # Fallback to sequential sweep
    for discrim in range(0, 10_000):
        exists = db_conn.query_row(discrim_exists_query, username, prefix, discrim)
        if not exists and locks.lock_discrim(username, prefix, discrim):
            return prefix, discrim, locks
    # Saturated usernames should be predicted by saturated prefixes
    # FIXME: log failure to generate discrim
    return -1, -1, locks


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
