import secrets
from random import randint
import uuid

def generate_user_id(db_conn):
    while 1:
        _id = secrets.randbits(64)
        check = db_conn.query_row("SELECT id FROM users WHERE id=?", _id)
        if not check:
            return _id

def generate_user_discrim(db_conn, username):
    check = db_conn.query("SELECT discrim FROM users WHERE _name = ?", username)
    if len(check) == 9999: # The username has hit its limit for discriminators
        _max = int(f"{str(len(check))}9") # Up the character limit +1
    elif check != None and len(check) != 0: # There are available discrims
        _discrims = [int(x) for x in check]
        _max = max(_discrims)
    elif check == None or len(check) == 0: # Nobody has used the username before, start out on the minimum for 4 char discrims
        _max = 9999 # Max combinations for 4 character discriminators
    while 1:
        _discrim = randint(1000, _max) # Minimum of 4 char discrims
        if _discrim == 1000:
            _discrim = '0001' # Congrats, you got a really rare discrim :)
        if _discrim not in db_conn.query("SELECT _name FROM users WHERE discrim = ?", _discrim): # username + discrim combo isnt taken
            return _discrim

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

