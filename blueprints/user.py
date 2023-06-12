
from sanic.blueprints import Blueprint
from sanic.response import json

from models.message import Message 
from sanic_openapi import doc

from utils import id_generator, checks, hashing

# Create the main blueprint to work with
blueprint = Blueprint('User_API', url_prefix="/user")

import time

@blueprint.get("/<thread_id:int>", strict_slashes=True)
@doc.summary("Fetches user information.")
def user_get(request, thread_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = db.query_row("SELECT id, _name FROM users WHERE id = ?" , thread_id) # TODO: logic for if you can get the users information.
    if not data:
        return json({"op": "void"}, status=404)
    return json(data, status=200)


@blueprint.post("/create", strict_slashes=True)
@doc.summary("Create a user.")
def user_create(request):
    db = request.ctx.db

    data = request.json
    if not all(k in data for k in ("username","auth")):
        return json({"op": "Missing required 'auth' or 'username' in JSON."})

    _id = id_generator.generate_user_id(db)

    password_obj = request.ctx.hasher.hash_password(data['auth']) 

    db.execute("INSERT INTO users (id, _name, authentication, salt, created_at) VALUES (?,?,?,?,?)" , _id, data["username"], password_obj.hash, password_obj.salt, time.time())
    return json({"op": "created.", "id": _id}, status=200)

@blueprint.post("/<thread_id:int>/add", strict_slashes=True) # TODO: add support for username
@doc.summary("Send friend request to user from ID.")
def user_friend_add(request, thread_id):
    db = request.ctx.db
    receiver = thread_id # For readability 

    data = request.json
    if not all(k in data for k in ("requester","auth")):
        return json({"op": "Missing required 'auth' or 'requester' in JSON."})
    auth, requester = data['auth'], data['requester']
    if int(requester) == thread_id:
        return json({"op": "Error. Not lonely enough to send friend requests to self"})

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, requester)): # The client is trying to send a request as a user they are not.
        return json({"op": "unauthorized."}, status=401)

    db.execute("INSERT INTO pendingFriendRequests (outgoingUserID, incomingUserID, start_timestamp) VALUES (?,?,?)", requester, receiver, time.time())
    return json({"op": "sent"}, status=200)

@blueprint.post("/<thread_id:int>/relationships", strict_slashes=True)
@doc.summary("Gets all relationships of a user.")
def user_relationships(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 

    data = request.json
    if not "auth" in data:
        return json({"op": "Missing required 'auth' in JSON."})
    auth = data['auth']

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, user)):
        return json({"op": "unauthorized."}, status=401)


    friends = db.query("SELECT userOneID,userTwoID FROM friends WHERE (userOneID = ? OR userTwoID = ?)", user, user)
    pending = db.query("SELECT outgoingUserID FROM pendingFriendRequests WHERE incomingUserID = ?", user)
    relationships = [("pending", x) for x in pending]
    for result in friends:
        if result["userOneID"] != thread_id:
            relationships.append(("friend", result["userOneID"]))
        elif result["userTwoID"] != thread_id:
            relationships.append(("friend", result["userTwoID"]))
    return json({"op": relationships}, status=200)

@blueprint.post("/accept", strict_slashes=True)
@doc.summary("Accept friend requests.")
def user_friend_accept(request):
    db = request.ctx.db

    data = request.json
    if not all(k in data for k in ("requester","auth","parent")):
        return json({"op": "Missing required 'auth' or 'requester' or 'parent' in JSON."})
    auth, requester, parent = data['auth'], data['requester'], data['parent']

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, parent)):
        return json({"op": "unauthorized."}, status=401)


    check = db.query("SELECT outgoingUserID FROM pendingFriendRequests WHERE incomingUserID = ? AND outgoingUserID = ?", parent, requester)
    if not check: # The friend request doesnt exist
        return json({"op": "void"}, status=404)
    check = db.query("SELECT * FROM friends WHERE (userOneID = ? AND userTwoID = ?)", parent, requester)
    if check:
        return json({"op": "already added"})
    db.execute("INSERT INTO friends (userOneID, userTwoID, start_timestamp) VALUES (?,?,?)", parent, requester, time.time())
    db.execute("DELETE FROM pendingFriendRequests WHERE incomingUserID = ? AND outgoingUserID = ?", parent, requester)
    return json({"op": "done"}, status=200)

@blueprint.delete("/<thread_id:int>/delete", strict_slashes=True)
@doc.summary("Deletes a user.")
def user_delete(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 

    data = request.json

    if not "auth" in data:
        return json({"op": "Missing required 'auth' in JSON."})


    if not checks.authenticated(data["auth"], id_generator.get_session_token(request.ctx.redis, user)):
        return json({"op": "unauthorized."}, status=401)

    db.execute("DELETE FROM users WHERE id = ?", user)
    return json({"op": "deleted"}, status=200)


@blueprint.post("/<thread_id:int>/authkey", strict_slashes=True)
@doc.summary("Generate an auth key for a user.") # Aka logging in.
def user_authkey(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 
    _json = request.json

    if not "auth" in _json:
        return json({"op": "Missing required 'auth' in JSON."})

    data = db.query_row("SELECT authentication, salt, created_at FROM users WHERE id = ?" , user)
    if not data:
        return json({"op": "void"}, status=404) # it doesnt exist

    check = request.ctx.hasher.verify_password_hash(_json['auth'], data['authentication'], data['salt']) # Verify their password is correct.

    if check != True: # the hash doesnt match
        return json({"op": "void"}, status=401)
    
    elif check == True: # the hash matches
        key = id_generator.generate_session_token(request.ctx.redis, user)
        return json({"op": "created", "authentication": key})
