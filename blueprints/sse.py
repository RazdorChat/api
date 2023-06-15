from sanic.blueprints import Blueprint
from websockets.exceptions import ConnectionClosed
from json import loads

from sanic_ext import openapi


from models.events import Event
from utils import checks

# Create the main blueprint to work with
blueprint = Blueprint('Events', url_prefix="/events")


## THIS IS LEGACY CODE, YOU SHOULD BE USING THE GOLANG WS SERVER ##

async def close(ws, msg):
    await ws.send(msg)
    await ws.close()

class FormatError(Exception):
    def __init__(self, message):            
        super().__init__(message)
        self.message = message

def format(raw_event_data, conn_ref: int, delim: str = "\n"): # This code is wacky...
    split = raw_event_data.split(delim) # Split the data by '\n', seperating the event and the data.
    loaded_json =  loads(split[1].split(":", 1)[1]) # Seperate the data tag from the actual json needed.
    if 'destination' in loaded_json.keys(): 
        try:
            destination = loaded_json['destination'].split(":", 1) # dest:destID
        except Exception as e:
            raise FormatError("Destination type (or ID) not specified") # One of the above was not there.
        if len(destination) != 2: # This shouldnt run, but i want to explicitly check anyways.
            raise FormatError("Destination type (or ID) not specified.")
        elif not checks.is_valid_destination(destination[0]): # Check if the event destination is valid.
            raise FormatError("Invalid Destination.")
    elif 'destination' not in loaded_json.keys(): # No destination.
        raise FormatError("No destination.")
    return Event(split[0].split(":", 1)[1], conn_ref, destination[1], destination[0], loaded_json)



@blueprint.websocket('/ws')
@openapi.exclude(False)
@openapi.summary("Live events with WS.")
@openapi.parameter(name="Authorization", schema=str, location="header", required=True)
@openapi.parameter(name="Author",        schema=str, location="header", required=True)
async def ws_recv(request, ws):
    try:
        if not request.headers.author or not request.headers.authorization or not request.headers: # Doesnt have the required headers.
            return await close(ws, "error: missing headers") # Missing headers

        given_auth_token, user_id = request.headers.authorization, request.headers.author
        real_auth_token = checks.ws_auth(request.ctx.redis, user_id, given_auth_token)

        if not real_auth_token: # Token does not exist, or is wrong.
            return await close(ws, "error: authentication error")

        await request.ctx.sse.register(int(user_id), ws) # Register the client for outgoing events under their auth token.
        await ws.send("recognized") # let the client know they are registered.
        while True:
            raw_event_data = await ws.recv() # Connection has sent a new event.
            if not checks.is_valid_event(raw_event_data):
                await ws.send("error: invalid event")
            # TODO: uncomment the below
            #try:
            else:
                event = format(raw_event_data, int(user_id))
                await request.ctx.sse.register_event(event) # Put the new event in the queue to send to other connections.
            #except Exception as e:
            #    print(f"Error registering event\n{e}")
            #except FormatError as e:
            #    await ws.send(Event("error", -1, {"error": f"{e.message}"}))
            #finally:
            await ws.send("done")
    except ConnectionClosed:
        pass
    finally:
        await request.ctx.sse.unregister(int(user_id)) # Unregister the client.

openapi.exclude(ws_recv)
