
from sanic.blueprints import Blueprint
from sanic.response import json

from utils import id_generator, checks

from models import events

from sanic_openapi import doc

from datetime import datetime

# Create the main blueprint to work with
blueprint = Blueprint('Message_API', url_prefix="/message")


@blueprint.get("/<thread_id:int>/get/<message_id:int>", strict_slashes=True)
@doc.summary("Fetches a message from a channel or DM.")
def message_get(request, thread_id, message_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = db.query_row("SELECT * FROM messages WHERE (DMChannelID = ? OR channelID = ?) AND id = ?" , thread_id, message_id)
    if not data:
        return json({"op": "void"}, status=404)
    return json(data, status=200)


@blueprint.delete("/<thread_id:int>/delete/<message_id:int>", strict_slashes=True)
@doc.summary("Deletes a message from a channel or DM.")
def message_delete(request, thread_id, message_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = db.query_row("SELECT id FROM messages WHERE (DMChannelID = ? OR channelID = ?) AND id = ?" , thread_id, thread_id, message_id)
    if not data:
        return json({"op": "void"}, status=404)


    if not checks.authenticated(request.json["auth"], id_generator.get_session_token(request.ctx.redis, request.json['author'])): # Client is trying to delete a message as a user they are not.
        return json({"op": "unauthorized."}, status=401)
    

    
    db.execute("DELETE FROM messages WHERE id = ?", message_id)
    return json({"op": "deleted."}, status=200)



@blueprint.post("/<thread_id:int>/create", strict_slashes=True)
@doc.summary("Send a message to a channel or DM.")
async def message_send(request, thread_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = request.json
    if {"author", "content"} <= data.keys():
        return json({"op": "Missing required JSON data."})

    if not checks.authenticated(request.json["auth"], id_generator.get_session_token(request.ctx.redis, data['author'])): # Client is trying to send a message as a user they are not.
        return json({"op": "unauthorized."}, status=401)

    _id = id_generator.generate_message_id(db) # Generate the UID  

    timestamp = datetime.now().timestamp()

    if db.query_row("SELECT id FROM DMChannels WHERE id = ?", channel_or_user): # its a DM channel (group chats)
        query = "INSERT INTO messages (id, authorID, DMChannelID, content, sent_timestamp) VALUES (?,?,?,?,?)"
    else: # its a normal channel (DMs and channels)
        query = "INSERT INTO messages (id, authorID, channelID, content, sent_timestamp) VALUES (?,?,?,?,?)"

    db.execute(query, _id, data['author'], thread_id, data['content'], timestamp)
    await request.ctx.sse.send_event(events.Event("new_message", 
        {
            "author": data['author'],
            "id": _id,
            "thread": thread_id,
            "content": data['content'],
            "timestamp": timestamp
        }
    ))
    return json(
        {"op": "sent"},
        status=200
    )


@blueprint.get("/<thread_id:int>/messages", strict_slashes=True)
@doc.summary("Fetches messages from a channel or DM.")
def message_mass_get(request, thread_id):
    db = request.ctx.db
    channel_or_user = thread_id # For readability 

    data = db.query("SELECT * FROM messages WHERE (DMChannelID = ? OR channelID = ?) ORDER BY sent_timestamp DESC LIMIT 100" , thread_id, thread_id)


    return json(data)