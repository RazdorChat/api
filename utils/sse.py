from asyncio import Queue, Lock, gather, QueueEmpty, sleep
from json import dumps

from models.events import Event
from utils.db import DB


class SSE: # TODO: rename to event handler
	def __init__(self, queue: Queue, db: DB) -> None:
		self.conns = dict()
		self.lock = Lock()
		self.queue = queue
		self.db = db

	def get_correct_connections(self, destination, destination_type, sending_conn_ref):
		match destination_type: # Since the destination is where the event is happening, we can just grab all users from the destination.
			case "guild":
				connections = self.db.query("SELECT user_id FROM guildusers WHERE parent_id = ?", destination)
			case "dmchannel":
				connections = self.db.query("SELECT user_id FROM dmchannelusers WHERE parent_id = ?", destination)
			case "user":
				connections = self.db.query("SELECT user_id FROM users WHERE parent_id = ?", destination)
			case _:
				raise Exception("Something went wrong matching the correct destination.")
		print(f"Destination: {destination}")
		print(f"Possible destination connections: {connections}")
		to_return = []
		for reference in connections:
			if reference in self.conns and not reference == sending_conn_ref:
				to_return.append(self.conns[reference])
		print(f"Online Connections: {to_return}")
		return to_return

	def format(self, event: Event):
		return f'event: {event.event}\ndata: {dumps(event.data)}'
		#return bytes(f"event: {event.event}\ndata: {event.data}\n\n", encoding='utf8')

	# TODO: Support for multiple connections per client.
	async def register(self, connection_reference, connection): # this is for registering clients 
		#await self.lock.acquire() # we cant insert while the push loop is running, or while there are are currently people in queue to register
		self.conns[connection_reference] = connection
		#await self.lock.release()

	# TODO: Support for multiple connections per client.
	async def unregister(self, connection_reference): # this is for unregistering clients
		#await self.lock.acquire() # we cant remove while the push loop is running, or while there are are currently people in queue to register/unregister
		self.conns.pop(connection_reference)
		#await self.lock.release()

	async def register_event(self, event: Event): # this is for internally putting an event into the queue 
		await self.queue.put(event)

	async def get_event(self): # this is for internally getting an event from the queue 
		try:
			await self.queue.get_nowait()
		except QueueEmpty:
			return None

	async def event_push_loop(self):
		print("Starting SSE task.")
		while True:
			try:
				data = self.queue.get_nowait() # Get new event if there is one.
			except QueueEmpty:
				pass
			else:

				coros = [conn.send(self.format(data)) for conn in self.get_correct_connections(data.destination, data.destination_type, data.conn_ref)] 
				await gather(*coros) # Send to all connections.
				print(f"Sent data to {len(coros)} connections.")
			finally:
				await sleep(0)
