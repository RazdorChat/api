from __future__ import annotations

from secrets import compare_digest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db import DBConnection
    from redis import Redis


VALID_EVENTS = {"new_message", "edit_message", "delete_message", "friend_request", "friend_request_reply", "friend_remove", "user_edit"}


def user_exists(db_conn: DBConnection, given_id: int) -> bool:
    """Checks if a user exists.

    Args:
            db_conn (object): DB connection object
            given_id (int): The ID of the user to check
    """
    check = db_conn.query_row("SELECT id FROM users WHERE id=?", given_id)
    if not check:  # user doesnt exist
        return False
    else:
        return True


def authenticated(given_auth_key: bytearray, real_auth_key: bytearray):  # Bit useless imo, just use compare_digest directly.
    # Helper tool to make sure a client has been given an auth key and it matches their real one.
    return compare_digest(given_auth_key, real_auth_key)


def check_impersonation(redis_conn: Redis, real_author_id: int | str, given_author_id: int | str):
    """Checks if a user is impersonating another user. (?)

    Args:
                        redis_conn (object): Redis connection object
                        real_author_id (int | str): The ID of the real author
                        given_author_id (int | str): The ID of the given author

    Returns:
                        bool: True if impersonating, False if not
    """
    # fresh from my ass, legacy code, i was high as fuck writing this and i dont even know where i was going
    real_token = redis_conn.get(real_author_id)
    check_token = redis_conn.get(given_author_id)
    if not real_token or not check_token:
        return None
    matches = compare_digest(real_token, check_token)
    if not matches:
        return True
    elif matches:
        return False


def has_shared_or_is_friend(db_conn):  # You cannot get user info for a user you dont share something with, nor DM them.
    pass


## THIS IS LEGACY CODE, YOU SHOULD BE USING THE GOLANG WS SERVER ##


def ws_auth(redis_conn: object, given_author_id: int | str, given_auth_token: str) -> tuple[str | None, bool]:
    """WS auth function.

    Args:
            redis_conn (object): Redis connection object
            given_author_id (int | str): Requesters ID
            given_auth_token (str): Requesters Token

    Returns:
            Tuple[str | None, bool]
    """
    real_token = redis_conn.get(given_author_id)
    if not real_token:  # The user has not authenticated. Possible impersonation. (they used a random ID/TOKEN, account is not logged in.)
        return None, False
    matches = compare_digest(given_auth_token, real_token)
    if not matches:  # The given token does not match. Possible impersonation. (targetted ID, random TOKEN, account is logged in.)
        return None, False
    return real_token, True


def is_valid_event(data: str, delim: str = "\n") -> bool | None:
    """Checks if event string is a valid event.

    Args:
            data (str): The string containing event data
            delim (str, optional): Delimiter for splitting the event string. Defaults to "\n".
    Returns:
            True | None: Returns True if the string contains a valid event, returns None if not.
    """
    event = data.split(delim, 1)[0].split(":")[1].strip()
    if event in VALID_EVENTS:
        return True


def is_valid_destination(destination):
    """Checks if destination is valid.

    Args:
            destination (str): The destination to check

    Returns:
            bool: True if valid, False if not
    """
    match destination.strip():
        case "guild":
            return True
        case "dmchannel":
            return True
        case "user":
            return True
        case _:
            return False
