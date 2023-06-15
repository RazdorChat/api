
from sanic.blueprints import Blueprint
from sanic.response import json

from models import ops, user

from sanic_ext import openapi

from utils import id_generator, checks, hashing

# Create the main blueprint to work with
blueprint = Blueprint('User', url_prefix="/user")

import time

@blueprint.get("/<thread_id:int>", strict_slashes=True)
@openapi.summary("User get")
@openapi.description("Fetches user information.")
@openapi.response(200, {"application/json" : user.User})
@openapi.response(404, {"application/json" : ops.Void})
def user_get(request, thread_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = db.query_row("SELECT id, _name FROM users WHERE id = ?" , thread_id) # TODO: logic for if you can get the users information.
    if not data:
        return json({"op": ops.Void.op}, status=404)
    return json({
        "id": data['id'],
        "name": data['_name']
    }, status=200)


@blueprint.post("/create", strict_slashes=True)
@openapi.body({"application/json": {"password": str, "username": str}})
@openapi.summary("User create")
@openapi.description("Create a user.")
@openapi.response(200, {"application/json" : ops.UserCreated})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(200, {"application/json" : ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_create(request):
    db = request.ctx.db

    data = request.json
    if not data:
        return json({"op": ops.MissingJson})

    if not all(k in data for k in ("username","password")):
        return json({"op": ops.MissingRequiredJson.op})

    _id = id_generator.generate_user_id(db)

    password_obj = request.ctx.hasher.hash_password(data['password']) 

    db.execute("INSERT INTO users (id, _name, authentication, salt, created_at) VALUES (?,?,?,?,?)" , _id, data["username"], password_obj.hash, password_obj.salt, time.time())
    return json({"op": ops.UserCreated.op, "id": _id}, status=200)

@blueprint.post("/<thread_id:int>/add", strict_slashes=True) # TODO: add support for username
@openapi.body({"application/json": {"auth": str, "requester": int}})
@openapi.summary("User friend")
@openapi.description("Send friend request to user from ID.")
@openapi.response(200, {"application/json" : ops.Sent})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(200, {"application/json" : ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_friend_add(request, thread_id):
    db = request.ctx.db
    receiver = thread_id # For readability 

    data = request.json
    if not data:
        return json({"op": ops.MissingJson})
    if not all(k in data for k in ("requester","auth")):
        return json({"op": ops.MissingRequiredJson.op})

    auth, requester = data['auth'], data['requester']
    if int(requester) == thread_id:
        return json({"op": "Error. Not lonely enough to send friend requests to self"}) # we do a little trolling

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, requester)): # The client is trying to send a request without auth.
        return json({"op": ops.Unauthorized.op}, status=401)

    db.execute("INSERT INTO pendingFriendRequests (outgoingUserID, incomingUserID, start_timestamp) VALUES (?,?,?)", requester, receiver, time.time())
    return json({"op": ops.Sent.op}, status=200)

@blueprint.post("/<thread_id:int>/relationships", strict_slashes=True)
@openapi.body({"application/json": {"auth": str}})
@openapi.summary("User relationship")
@openapi.description("Gets all relationships of a user.")
@openapi.response(200, {"application/json" : {"op": list[ops.Relationship]}})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_relationships(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 

    data = request.json
    if not data:
        return json({"op": ops.MissingJson.op})
    if not "auth" in data:
        return json({"op": ops.MissingJson.op})
    auth = data['auth']

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, user)):
        return json({"op": "unauthorized."}, status=401)


    friends = db.query("SELECT userOneID,userTwoID FROM friends WHERE (userOneID = ? OR userTwoID = ?)", user, user)
    pending = db.query("SELECT outgoingUserID FROM pendingFriendRequests WHERE incomingUserID = ?", user)
    relationships = {}
    for x in pending: relationships[x] = "pending"
    for result in friends:
        if result["userOneID"] != thread_id:
            relationships[result["userOneID"]] = "friend"
        elif result["userTwoID"] != thread_id:
            relationships[ result["userTwoID"]] = "friend"
    return json({"op": relationships}, status=200)

@blueprint.post("/accept", strict_slashes=True)
@openapi.body({"application/json": {"auth": str, "requester": int, "parent": int}})
@openapi.summary("User friend accept")
@openapi.description("Accept friend requests.")
@openapi.response(200, {"application/json" : ops.Done.op})
@openapi.response(200, {"application/json" : ops.AlreadyAdded.op})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(200, {"application/json" : ops.MissingRequiredJson})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_friend_accept(request):
    db = request.ctx.db

    data = request.json
    if not data:
        return json({"op": ops.MissingJson})
    if not all(k in data for k in ("requester","auth","parent")):
        return json({"op": ops.MissingRequiredJson})
    auth, requester, parent = data['auth'], data['requester'], data['parent']

    if not checks.authenticated(auth, id_generator.get_session_token(request.ctx.redis, parent)):
        return json({"op": ops.Unauthorized.op}, status=401)


    check = db.query("SELECT outgoingUserID FROM pendingFriendRequests WHERE incomingUserID = ? AND outgoingUserID = ?", parent, requester)
    if not check: # The friend request doesnt exist
        return json({"op": ops.Void.op}, status=404)
    check = db.query("SELECT * FROM friends WHERE (userOneID = ? AND userTwoID = ?)", parent, requester)
    if check:
        return json({"op": ops.AlreadyAdded})
    db.execute("INSERT INTO friends (userOneID, userTwoID, start_timestamp) VALUES (?,?,?)", parent, requester, time.time())
    db.execute("DELETE FROM pendingFriendRequests WHERE incomingUserID = ? AND outgoingUserID = ?", parent, requester)
    return json({"op": ops.Done.op}, status=200)

@blueprint.delete("/<thread_id:int>/delete", strict_slashes=True)
@openapi.body({"application/json": {"auth": str}})
@openapi.summary("User delete")
@openapi.description("Deletes a user.")
@openapi.response(200, {"application/json" : ops.Deleted})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(200, {"application/json" : ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_delete(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 

    data = request.json
    if not data:
        return json({"op": ops.MissingJson.op})

    if not "auth" in data:
        return json({"op": ops.MissingRequiredJson.op})


    if not checks.authenticated(data["auth"], id_generator.get_session_token(request.ctx.redis, user)):
        return json({"op": ops.Unauthorized.op}, status=401)

    db.execute("DELETE FROM users WHERE id = ?", user)
    return json({"op": ops.Deleted.op}, status=200)


@blueprint.post("/<thread_id:int>/authkey", strict_slashes=True)
@openapi.body({"application/json": {"auth": str}})
@openapi.summary("User authkey")
@openapi.description("Generate an auth key for a user.") # Aka logging in.
@openapi.response(200, {"application/json" : ops.UserAuthkeyCreated})
@openapi.response(200, {"application/json" : ops.MissingJson})
@openapi.response(200, {"application/json" : ops.MissingRequiredJson})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def user_authkey(request, thread_id):
    db = request.ctx.db
    user = thread_id # For readability 
    _json = request.json
    if not _json:
        return json({"op": ops.MissingJson.op})

    if not "auth" in _json:
        return json({"op": ops.MissingRequiredJson.op})

    data = db.query_row("SELECT authentication, salt, created_at FROM users WHERE id = ?" , user)
    if not data:
        return json({"op": ops.Void.op}, status=404) # it doesnt exist

    check = request.ctx.hasher.verify_password_hash(_json['auth'], data['authentication'], data['salt']) # Verify their password is correct.

    if check != True: # the hash doesnt match
        return json({"op": ops.Unauthorized.op}, status=401)
    
    elif check == True: # the hash matches
        key = id_generator.generate_session_token(request.ctx.redis, user)
        return json({"op": ops.UserAuthkeyCreated.op, "authentication": key})
