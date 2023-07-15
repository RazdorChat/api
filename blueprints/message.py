
from sanic.blueprints import Blueprint
from sanic.response import json

from utils import id_generator, checks

from models import events, message, ops

from sanic_ext import openapi


from datetime import datetime

# Create the main blueprint to work with
blueprint = Blueprint('Message', url_prefix="/message")

valid_dest_types = { # TODO: change this to something less weird
    "dmchannel": "SELECT * FROM DMChannelmessages WHERE DMChannelID = ? AND id = ?",
    "channel":  "SELECT * FROM messages WHERE channelID = ? AND id = ?",
    "user":  "SELECT * FROM DMmessages WHERE DmID = ? AND id = ?",
    "mass": {
        "dmchannel": "SELECT * FROM DMChannelmessages WHERE DMChannelID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100",
        "channel":  "SELECT * FROM messages WHERE channelID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100",
        "user":  "SELECT * FROM DMmessages WHERE DmID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100"
    }
}

user_dest_check = "SELECT id FROM DMs WHERE (UserOneID = ? AND UserTwoID = ?) or (UserTwoID = ? AND UserOneID = ?)"

@blueprint.get("/<thread_type:str>/<thread_id:int>/get/<message_id:int>", strict_slashes=True, ignore_body=False)
@openapi.body({"application/json": {"requester": int}})
@openapi.description("Fetches a message from a channel or DM.")
@openapi.response(200, {"application/json" : message.Message})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : {"op": "Invalid thread type."}}) # TODO: convert to ops formatting like normal.
@openapi.response(404, {"application/json" : ops.Void})
def message_get(request, thread_type, thread_id, message_id):
    db = request.ctx.db

    _json = request.json
    if not _json:
        return json({"op": ops.MissingJson.op})

    if not "requester" in _json:
        return json({"op": ops.MissingRequiredJson.op})

    if thread_type not in valid_dest_types:
        return json({"op": "Invalid thread type."})
    query = valid_dest_types[thread_type]

    # TODO: CHECK IF USER CAN GET MESSAGES

    if thread_type == "user":
        check = db.query_row(user_dest_check, thread_id, _json["requester"], thread_id, _json["requester"])
        if not check: # Dms dont exist
            return json({"op": ops.Void.op}, status=404)

        data = db.query_row(query, check, message_id) 
    else:
        data = db.query_row(query, thread_id, message_id)

    if not data:
        return json({"op": ops.Void.op}, status=404)


    if check:
        dest = check
    else:
        dest = thread_id

    return json({
            "id": data['id'],
            "author":data['authorID'],
            "thread": dest,
            "content": data['content'],
            "timestamp": data['sent_timestamp']
        }, status=200)


@blueprint.delete("/<thread_type:str>/<thread_id:int>/delete/<message_id:int>", strict_slashes=True)
@openapi.body({"application/json": {"auth": str, "requester": int}})
@openapi.description("Deletes a message from a channel or DM.")
@openapi.response(200, {"application/json" : ops.Deleted})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def message_delete(request, thread_type, thread_id, message_id):
    db = request.ctx.db

    if thread_type not in valid_dest_types:
        return json({"op": "Invalid thread type."})
    query = valid_dest_types[thread_type]

    _json = request.json
    if not _json:
        return json({"op": ops.MissingJson.op})

    if not all(k in data for k in ("requester", "auth")):
        return json({"op": ops.MissingRequiredJson.op})

    if thread_type == "user":
        data = db.query_row(query, thread_id, thread_id, message_id) # TODO/BUG: unknown behavior, it is giving it the same ID for UserOne and UserTwo, might need to require a requester (author) ID for this.
    else:
        data = db.query_row(query, thread_id, message_id)
    if not data:
        return json({"op": ops.Void.op}, status=404)


    if not checks.authenticated(_json["auth"], id_generator.get_session_token(request.ctx.redis, _json['requester'])): # Client is trying to delete a message as a user they are not.
        return json({"op": ops.Unauthorized.op}, status=401)



    db.execute("DELETE FROM messages WHERE id = ?", message_id)
    return json({"op": ops.Deleted.op}, status=200)



@blueprint.post("/<thread_type:str>/<thread_id:int>/create", strict_slashes=True)
@openapi.body({"application/json": {"auth": str, "requester": int, "content": str}})
@openapi.description("Send a message to a channel or DM, specified with thread_type.")
@openapi.response(200, {"application/json" : ops.Sent})
@openapi.response(400, {"application/json" : {"op": "Invalid thread type."}}) # TODO: convert to ops formatting like normal.
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
async def message_send(request, thread_type, thread_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability

    if thread_type not in valid_dest_types:
        return json({"op": "Invalid thread type."})

    data = request.json
    if not data:
        return json({"op": ops.MissingJson.op})
    if not all(k in data for k in ("requester","content", "auth")):
        return json({"op": ops.MissingRequiredJson.op})

    if not checks.authenticated(request.json["auth"], id_generator.get_session_token(request.ctx.redis, data['requester'])): # Client is trying to send a message as a user they are not, or their auth is wrong.
        return json({"op": ops.Unauthorized.op}, status=401)

    _id = id_generator.generate_message_id(db) # Generate the ID

    timestamp = datetime.now().timestamp()
    check = None

    if thread_type == "dmchannel": # TODO: make sure they exist outside of just the user thread type
         db.execute("INSERT INTO DMChannelmessages (id, authorID, DMChannelID, content, sent_timestamp) VALUES (?,?,?,?,?)", _id, data['requester'], thread_id, data['content'], timestamp)
    elif thread_type == "user":
        if not checks.user_exists(db, thread_id): # User has to exist
            return json({"op": ops.Void.op}, status=404)
        check = db.query_row(user_dest_check, thread_id, data["requester"], thread_id, data["requester"])
        print(check)
        if not check: # Dms dont exist, make them.
            dm_id = id_generator.generate_dm_id(db)
            db.execute("INSERT INTO DMs (id, UserOneID, UserTwoID) VALUES (?,?,?)", dm_id, data['requester'], thread_id)

        db.execute("INSERT INTO DMmessages (id, authorID, DmID, content, sent_timestamp) VALUES (?,?,?,?,?)", _id, data['requester'], check, data['content'], timestamp)
    elif thread_type == "guild":
        db.execute("INSERT INTO messages (id, authorID, channelID, content, sent_timestamp) VALUES (?,?,?,?,?)", _id, data['requester'], thread_id, data['content'], timestamp)
    if check:
        thread_id = check

    await request.ctx.sse.register_event(events.Event("new_message", int(data['requester']), thread_id, thread_type,
        {
            "author": data['requester'],
            "id": _id,
            "thread": thread_id,
            "content": data['content'],
            "timestamp": timestamp
        }
    ))
    return json(
        {"op": ops.Sent.op},
        status=200
    )


@blueprint.get("/<thread_type:str>/<thread_id:int>/messages", strict_slashes=True, ignore_body=False)
@openapi.body({"application/json": {"auth": str, "requester": int}})
@openapi.description("Fetches messages from a channel or DM.")
@openapi.response(400, {"application/json" : {"op": "Invalid thread type."}}) # TODO: convert to ops formatting like normal.
@openapi.response(200, {"application/json" : {"msgs": list[message.Message]}})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
@openapi.response(404, {"application/json" : ops.Void})
def message_mass_get(request, thread_type, thread_id):
    db = request.ctx.db
    if thread_type not in valid_dest_types["mass"]:
        return json({"op": "Invalid thread type."})

    data = request.json
    if not data:
        return json({"op": ops.MissingJson.op})
    if not all(k in data for k in ("requester", "auth")):
        return json({"op": ops.MissingRequiredJson.op})

    if not checks.authenticated(request.json["auth"], id_generator.get_session_token(request.ctx.redis, request.json["requester"])): # Client is trying to send a message as a user they are not, or their auth is wrong.
        return json({"op": ops.Unauthorized.op}, status=401)

    # TODO: CHECK IF USER CAN GET MESSAGES

    if thread_type == "user":
        check = db.query_row(user_dest_check, thread_id, data["requester"], thread_id, data["requester"])
        if not check: # Dms dont exist
            return json({"op": ops.Void.op}, status=404)

        _data = db.query(valid_dest_types["mass"][thread_type], check)
    else:
        check = None
        _data = db.query(valid_dest_types["mass"][thread_type], thread_id)

    if not _data:
        return json({"op": ops.Void.op}, status=404)

    messages = []
    for msg in _data:
        if check:
            thread_id = check
        messages.append({
            "id": msg['id'],
            "author": msg['authorID'],
            "thread": thread_id,
            "content": msg['content'],
            "timestamp": msg['sent_timestamp']
        })

    if len(messages) == 0:
        return json({"op": ops.Void.op}, status=404)

    return json({"msgs": messages})