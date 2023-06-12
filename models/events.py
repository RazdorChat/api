from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    event: str
    conn_ref: int
    destination: int
    destination_type: str 
    data: dict | None = None

@dataclass
class Heartbeat:
    ...