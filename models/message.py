from dataclasses import dataclass

from models.user import User
from models.channel import Channel, DMChannel


@dataclass
class Message:
    id: int
    author: User
    thread: Channel | DMChannel
    parent_id: int
    content: str
    timestamp: float