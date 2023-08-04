from sanic.blueprints import Blueprint
from websockets.exceptions import ConnectionClosed
from datetime import datetime

from sanic_ext import openapi


from models.events import Event
from utils import checks, id_generator

# Create the main blueprint to work with
blueprint = Blueprint('Events', url_prefix="/events")


## THIS IS LEGACY CODE, YOU SHOULD BE USING THE GOLANG WS SERVER ##

class FormatError(Exception):
	def __init__(self, message):            
		super().__init__(message)
		self.message = message

async def close(ws, msg):
	await ws.send(msg)
	await ws.close()


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
		real_auth_token = checks.ws_auth(request.app.ctx.redis, user_id, given_auth_token)

		if not real_auth_token: # Token does not exist, or is wrong.
			return await close(ws, "error: authentication error")

		await request.app.ctx.sse.register(int(user_id), ws) # Register the client for outgoing events under their auth token.
		await ws.send("recognized") # let the client know they are registered.
		while True:
			raw_event_data = await ws.recv() # Connection has sent a new event.
			if not checks.is_valid_event(raw_event_data):
				await ws.send("error: invalid event")
			else:
				try:
					event = format(raw_event_data, int(user_id))
					if event.event == "new_message":
						if event.data["author"] != user_id:
							return await close(ws, "error: author ID not the same as given ID in headers") # TODO: handle better than just closing
						if event.destination_type == "dmchannel":
							query = "INSERT INTO messages (id, authorID, DMChannelID, content, sent_timestamp) VALUES (?,?,?,?,?)"
						elif event.destination_type == "user":
							query = "INSERT INTO messages (id, authorID, userID, content, sent_timestamp) VALUES (?,?,?,?,?)"
						elif event.destination_type == "guild":
							query = "INSERT INTO messages (id, authorID, channelID, content, sent_timestamp) VALUES (?,?,?,?,?)"

						_id = id_generator.generate_message_id(request.app.ctx.db) # Generate the UID 
						timestamp = datetime.now().timestamp()

						request.app.ctx.db.execute(query, _id, user_id, event.data["thread"], event.data["content"], timestamp)
					await request.app.ctx.sse.register_event(event) # Put the new event in the queue to send to other connections.
				except FormatError as e:
					await ws.send(Event("error", -1, {"error": f"{e.message}"}))
				except Exception as e:
					print(f"Error registering event\n{e}")
			await ws.send("done")
	except ConnectionClosed:
		pass
	finally:
		await request.app.ctx.sse.unregister(int(user_id)) # Unregister the client.

openapi.exclude(ws_recv)
