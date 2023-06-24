
from sanic.blueprints import Blueprint
from sanic.response import json

from utils import id_generator, checks

from models import events, message, ops

from sanic_ext import openapi


from datetime import datetime

# Create the main blueprint to work with
blueprint = Blueprint('Message', url_prefix="/message")

# TODO: Format messaging like so
# /message/guild/<thread_id:int>/*
# /message/user/<thread_id:int>/*
# /message/dmchannel/<thread_id:int>/*

valid_dest_types = {
    "dmchannel": "SELECT * FROM messages WHERE DMChannelID = ? AND id = ?",
    "channel":  "SELECT * FROM messages WHERE channelID = ? AND id = ?",
    "user":  "SELECT * FROM messages WHERE userID = ? AND id = ?",
    "mass": {
        "dmchannel": "SELECT * FROM messages WHERE DMChannelID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100",
        "channel":  "SELECT * FROM messages WHERE channelID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100",
        "user":  "SELECT * FROM messages WHERE userID = ? ORDER BY (`sent_timestamp`=0) DESC,`sent_timestamp` DESC LIMIT 100"
    }
}


@blueprint.get("/<thread_id:int>/get/<message_id:int>/<thread_type:str>", strict_slashes=True, ignore_body=False)
@openapi.description("Fetches a message from a channel or DM.")
@openapi.response(200, {"application/json" : message.Message})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : {"op": "Invalid thread type."}}) # TODO: convert to ops formatting like normal.
@openapi.response(404, {"application/json" : ops.Void})
def message_get(request, thread_id, message_id, thread_type):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    
    if thread_type not in valid_dest_types:
        return json({"op": "Invalid thread type."})
    query = valid_dest_types[thread_type]

    data = db.query_row(query, thread_id, message_id)
    if not data:
        return json({"op": ops.Void.op}, status=404)
    
    _dest = [data['userID'], data['DMChannelID'], data['channelID']]
    dest = [x for x in _dest if x != None]

    return json({
            "id": data['id'],
            "author":data['authorID'],
            "thread": dest[0],
            "content": data['content'],
            "timestamp": data['sent_timestamp']
        }, status=200)


@blueprint.delete("/<thread_id:int>/delete/<message_id:int>", strict_slashes=True)
@openapi.body({"application/json": {"auth": str, "requester": int}})
@openapi.description("Deletes a message from a channel or DM.")
@openapi.response(200, {"application/json" : ops.Deleted})
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(400, {"application/json" : ops.MissingRequiredJson})
@openapi.response(404, {"application/json" : ops.Void})
@openapi.response(401, {"application/json" : ops.Unauthorized})
def message_delete(request, thread_id, message_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 
    _json = request.json
    if not _json:
        return json({"op": ops.MissingJson.op})

    if not all(k in data for k in ("requester", "auth")):
        return json({"op": ops.MissingRequiredJson.op})

    data = db.query_row("SELECT id FROM messages WHERE (DMChannelID = ? OR channelID = ?) AND id = ?" , thread_id, thread_id, message_id)
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
@openapi.response(400, {"application/json" : ops.MissingJson})
@openapi.response(404, {"application/json" : ops.Void})
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
        return json({"op": ops.MissingRequiredJson})

    if not checks.authenticated(request.json["auth"], id_generator.get_session_token(request.ctx.redis, data['requester'])): # Client is trying to send a message as a user they are not, or their auth is wrong.
        return json({"op": ops.Unauthorized}, status=401)

    _id = id_generator.generate_message_id(db) # Generate the UID  

    timestamp = datetime.now().timestamp()

    if thread_type == "dmchannel":
        dest_type = "dmchannel"
        query = "INSERT INTO messages (id, authorID, DMChannelID, content, sent_timestamp) VALUES (?,?,?,?,?)"
    elif thread_type == "user":
        dest_type = "user"
        query = "INSERT INTO messages (id, authorID, userID, content, sent_timestamp) VALUES (?,?,?,?,?)"
    elif thread_type == "guild":
        dest_type = "guild"
        query = "INSERT INTO messages (id, authorID, channelID, content, sent_timestamp) VALUES (?,?,?,?,?)"

    db.execute(query, _id, data['requester'], thread_id, data['content'], timestamp)

    await request.ctx.sse.register_event(events.Event("new_message", int(data['requester']), thread_id, dest_type, 
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


@blueprint.get("/<thread_type:str>/<thread_id:int>/messages", strict_slashes=True)
@openapi.description("Fetches messages from a channel or DM.")
@openapi.response(400, {"application/json" : {"op": "Invalid thread type."}}) # TODO: convert to ops formatting like normal.
@openapi.response(200, {"application/json" : {"msgs": list[message.Message]}})
def message_mass_get(request, thread_type, thread_id):
    db = request.ctx.db
    if thread_type not in valid_dest_types:
        return json({"op": "Invalid thread type."})

    data = db.query(valid_dest_types["mass"][thread_type], thread_id)


    return json({"msgs": data})