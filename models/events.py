from dataclasses import dataclass


@dataclass
class Event:
    event: str  # TODO: change to ints
    conn_ref: int
    destination: int | None
    destination_type: str | None
    data: dict | None = None


@dataclass
class Heartbeat:
    ...
