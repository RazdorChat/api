from __future__ import annotations

from asyncio import Lock, Queue, QueueEmpty, gather, sleep
from json import dumps

from models.events import Event
from utils.db import DB


class SSE:  # TODO: rename to event handler
    """Handles sending events to clients.

    Args:
        queue (Queue): The queue to get events from.
        db (DB): The database connection to use.

    """

    def __init__(self, queue: Queue, db: DB) -> None:
        self.conns = dict()
        self.lock = Lock()
        self.queue = queue
        self.db = db

    def get_correct_connections(self, destination, destination_type, sending_conn_ref):
        """This gets the correct connections to send the event to, that way we arent sending events to people who should not be getting them,
        for example: someone receiving a message for a server they arent in at all.

        Args:
            destination (str | int): The ID of the destination.
            destination_type (str): The type of the destination.
            sending_conn_ref: The connection reference of the connection that sent the event.

        """
        match destination_type:  # Since the destination is where the event is happening, we can just grab all users from the destination.
            case "guild":
                connections = self.db.query("SELECT user_id FROM guildusers WHERE parent_id = ?", destination)
            case "dmchannel":
                connections = self.db.query("SELECT user_id FROM dmchannelusers WHERE parent_id = ?", destination)
            case "user":
                connections = self.db.query("SELECT id FROM users WHERE id = ?", destination)
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
        """Formats an event into a string.

        Args:
            event (Event): The event to format.
        """
        return f"event: {event.event}\ndata: {dumps(event.data)}"
        # return bytes(f"event: {event.event}\ndata: {event.data}\n\n", encoding='utf8')

    # TODO: Support for multiple connections per client.
    async def register(self, connection_reference, connection):
        """Registers a client to the SSE handler.

        Args:
            connection_reference: The reference to the connection.
            connection: The connection to register.
        """
        # await self.lock.acquire() # we cant insert while the push loop is running, or while there are are currently people in queue to register
        self.conns[connection_reference] = connection
        # await self.lock.release()

    async def unregister(self, connection_reference):
        """Unregisters a client from the SSE handler.

        Args:
            connection_reference: The reference to the connection.
        """
        # await self.lock.acquire() # we cant remove while the push loop is running, or while there are are currently people in queue to register/unregister
        del self.conns[
            connection_reference
        ]  # BUG?: erroring? im not removing it anywhere else, watch for if this errors after changing to del
        # await self.lock.release()

    async def register_event(self, event: Event):  # this is for internally putting an event into the queue
        """Registers an event to the queue.

        Args:
            event (Event): The event to register.
        """
        await self.queue.put(event)

    async def get_event(self):  # this is for internally getting an event from the queue
        """Gets an event from the queue.

        Returns:
            Event: The event that was gotten or None if there was no event.
        """
        try:
            await self.queue.get_nowait()
        except QueueEmpty:
            return None

    async def event_push_loop(self):
        while True:
            try:
                data = await self.queue.get()  # Get new event if there is one.
            except QueueEmpty:
                pass
            else:
                coros = [
                    conn.send(self.format(data))
                    for conn in self.get_correct_connections(data.destination, data.destination_type, data.conn_ref)
                ]
                await gather(*coros)  # Send to all connections.
                print(f"Sent data to {len(coros)} connections.")
            finally:
                await sleep(0)
