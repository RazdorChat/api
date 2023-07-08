from dataclasses import dataclass
from typing import Optional


@dataclass
class Event:
    event: str # TODO: change to ints
    conn_ref: int
    destination: int
    destination_type: str 
    data: dict | None = None

@dataclass
class Heartbeat:
    ...