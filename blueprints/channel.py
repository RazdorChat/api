from typing import TYPE_CHECKING

from sanic.blueprints import Blueprint
from sanic.response import json
from sanic_ext import openapi

from models import events, ops
from utils import id_generator

if TYPE_CHECKING:
    from sanic.request import Request
    from sanic.response import JSONResponse

    from context import CustomContext
    from utils.db import DB

# Create the main blueprint to work with
blueprint = Blueprint("Channel", url_prefix="/channel")


async def channel_create_dm(ctx: CustomContext, data: dict, db: DB) -> JSONResponse:
    """Creates a DM channel.

    Args:
                ctx (CustomContext): The context to use.
                data (dict): The data to use.
                db (DB): The database to use.

    Returns:
                JSONResponse: The response to send to the client.
    """
    participants = data["participants"]

    if not all(isinstance(x, int) for x in participants):  # Participants need to be integers, as they are all user IDs.
        return json({"op": ops.MalformedJson.op})

    # Check if the user has relations to anyone being added
    for user_id in participants:  # TODO: Add to checks.py
        is_friend = db.query_row(
            "SELECT userOneID,userTwoID FROM friends WHERE (userOneID = ? OR userTwoID = ?)", data["requester"], user_id
        )
        if not is_friend:
            return json({"op": ops.Unauthorized.op})

    _id = id_generator.generate_channel_id(db, "dmchannel")

    db.execute("INSERT INTO dmchannels (id) VALUES (?)", _id)  # Create the channel.

    for user_id in participants:  # Add all the users they are trying to add.
        db.execute("INSERT INTO dmchannelusers (parent_id, user_id) VALUES (?,?)", _id, user_id)

    # Add the creator themself.
    db.execute("INSERT INTO dmchannelusers (parent_id, user_id) VALUES (?,?)", _id, data["requester"])

    # Notify participants of being added.
    await ctx.sse.register_event(
        events.Event(
            "dmchannel_add", int(data["requester"]), _id, "dmchannel", {"id": _id, "participants": [int(uid) for uid in participants]}
        )
    )

    return json({"op": ops.DmChannelCreated.op, "id": _id})


valid_thread_creation_types = {  # Weird way to do this, i should change it later.
    "guild": None,
    "category": None,
    "dmchannel": channel_create_dm,
}


@blueprint.post("/<thread_type:str>create", strict_slashes=True)
@openapi.body({"application/json": {"auth": str, "requester": int, "name": str, "participants": list[int]}})
@openapi.description(
    "Create a channel of the type `thread_type` (participants is only for `dmchannel` type, and `name` is ignored for now)."
)
@openapi.response(400, {"application/json": ops.DmChannelCreated})  # TODO: add other channel created OPs
@openapi.response(400, {"application/json": {"op": "Invalid thread type."}})  # TODO: convert to ops formatting like normal.
@openapi.response(400, {"application/json": ops.MissingJson})
@openapi.response(400, {"application/json": ops.MissingRequiredJson})
@openapi.response(400, {"application/json": ops.MalformedJson})
@openapi.response(401, {"application/json": ops.Unauthorized})
async def channel_create(request: Request, thread_type: str) -> JSONResponse:
    """Creates a channel of the type `thread_type`.

    Args:
        request (Request): The request that caused the exception.
        thread_type (str): The type of thread to create. Should be one of the following: `guild`, `category`, `dmchannel`.
                           Currently only `dmchannel` is supported.

    Returns:
        JSONResponse: The response to send to the client.
    """
    db = request.app.ctx.db
    data = request.json
    if not data:
        return json({"op": ops.MissingJson})

    if not all(k in data for k in ("auth", "requester", "name")):
        return json({"op": ops.MissingRequiredJson.op})

    if thread_type not in valid_thread_creation_types:
        return json({"op": "Invalid thread type."})

    return valid_thread_creation_types[thread_type](
        request.app.ctx, data, db
    )  # Call the correct function for the thread type, allowing for one endpoint.
