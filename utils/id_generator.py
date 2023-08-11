import secrets
from random import randint
from typing import Tuple
from utils.redis import RDB

def generate_user_id(db_conn):
    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM users WHERE id=?", _id)
        if not check:
            return _id

# Determine or generate user discriminator prefix
def _generate_user_discrim_prefix(db_conn, username: str) -> int:
    try_random_passes = 5
    prefix_count_query = 'SELECT COUNT(discrim) FROM users WHERE _name = ? AND discrim_prefix = ?'
    # If a 4-digit discrim can be used, return a discrim_prefix of 0 
    if db_conn.query_row(prefix_count_query, username, 0) < 10_000:
        return 0
    # Get prefix from redis if it exists
    redis_key = f'username:{username}:fill_discrim_prefix'
    redis_prefix = RDB.get(redis_key)
    if redis_prefix is not None:
        count = db_conn.query_row(prefix_count_query, username, redis_prefix)
        if count < 10_000:
            return int(redis_prefix)
    # Generate a new nonzero discrim_prefix
    for _ in range(try_random_passes): # Try to generate a random prefix to avoid leaking username popularity info
        prefix = randint(10, 99)
        count = db_conn.query_row(prefix_count_query, username, prefix)
        if count == 10_000:
            continue
        # Once a discrim prefix is half full, use it exclusively until full
        if count >= 5000:
            RDB.set(redis_key, str(prefix))
        # TODO: redlock nearly-full prefixes
        return prefix
    # If a random prefix couldn't be chosen, do a sequential sweep to find the lowest prefix available
    # When a prefix is chosen via this method, it will be assigned to fill_discrim_prefix in redis
    for prefix in range(10, 100):
        count = db_conn.query_row(prefix_count_query, username, prefix)
        if count == 10_000:
            continue
        RDB.set(redis_key, str(prefix))
        # TODO: redlock nearly-full prefixes
        return prefix
    return -1 # -1 is returned if a username has no possible discrim prefixes left, and thus no possible discriminators

# Generate a discriminator
# The first int in the tuple returned is the discrim_prefix, the second is the discrim
# If either value is negative, generation has failed 
def generate_user_discrim(db_conn, username) -> Tuple[int, int]:
    try_random_passes = 5
    # Determine discrim_prefix 
    prefix = _generate_user_discrim_prefix(db_conn, username)
    if prefix == -1:
        # Return -1 to signal that a username is totally saturated (all 900k possible discrims are saturated,
        # which can be determined from all 90 possible discrims being saturated)
        return (-1, -1)
    discrim_exists_query = 'SELECT EXISTS(SELECT 1 FROM users WHERE _name = ? AND discrim_prefix = ? AND discrim = ?)'
    # Try to randomly generate discrim
    for _ in range(try_random_passes):
        discrim = randint(0, 9999)
        exists = db_conn.query_row(discrim_exists_query, username, prefix, discrim)
        if not exists:
            # TODO: redlock discrim
            return (prefix, discrim)
    # Fallback to sequential sweep
    for discrim in range(0, 10_000):
        exists = db_conn.query_row(discrim_exists_query, username, prefix, discrim)
        if not exists:
            # TODO: redblock discrim
            return (prefix, discrim)
    # Saturated usernames should be predicted by saturated prefixes
    # FIXME: log failure to generate discrim
    return (-1, -1)

def generate_message_id(db_conn):
    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM messages WHERE id=?", _id)
        if not check:
            return _id

def generate_dm_id(db_conn):
    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM DMs WHERE id=?", _id)
        if not check:
            return _id

def generate_session_token(redis_conn, author_id):
    token = redis_conn.get(author_id)
    if not token:
        token = secrets.token_urlsafe(32)
        redis_conn.set(author_id, token)
    return token

def get_session_token(redis_conn, author_id):
    data = redis_conn.get(author_id)
    if not data:
        return "fake_data_none"
    return data

