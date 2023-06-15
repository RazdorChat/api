from secrets import compare_digest

valid_events = {
    "new_message",
    "edit_message",
    "delete_message",
    "friend_request",
    "friend_request_reply",
    "friend_remove",
    "user_edit"
}

def authenticated(given_auth_key: bytearray, real_auth_key: bytearray): # Helper tool to make sure a client has been given an auth key and it matches their real one.
    result = compare_digest(given_auth_key, real_auth_key)
    return compare_digest(given_auth_key, real_auth_key)
    

def check_impersonation(redis_conn, given_author_id, real_author_id): # fresh from my ass, legacy code, i was high as fuck writing this and i dont even know where i was going
    real_token = redis_conn.get(real_author_id)
    check_token = redis_conn.get(given_author_id)
    if not real_token or not check_token:
        return None
    matches = compare_digest(real_token, check_token)
    if not matches:
        return True
    elif matches:
        return False
 
def has_shared_or_is_friend(db_conn): # You cannot get user info for a user you dont share something with, nor DM them.
    pass


## THIS IS LEGACY CODE, YOU SHOULD BE USING THE GOLANG WS SERVER ##

def ws_auth(redis_conn, given_author_id, given_auth_token):
    real_token = redis_conn.get(given_author_id)
    if not real_token: # The user has not authenticated. Possible impersonation. (they used a random ID/TOKEN, account is not logged in.)
        return None, False
    matches = compare_digest(given_auth_token, real_token)
    if not matches:  # The given token does not match. Possible impersonation. (targetted ID, random TOKEN, account is logged in.)
        return None, False
    return real_token, True


def is_valid_event(data, delim: str = "\n"):
    event = data.split(delim, 1)[0].split(":")[1].strip()
    if event in valid_events:
        return True
        
def is_valid_destination(destination):
    match destination.strip():
        case "guild":
            return True
        case "dmchannel":
            return True
        case "user":
            return True
        case _:
            return False