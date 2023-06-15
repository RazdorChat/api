from dataclasses import dataclass

@dataclass
class Message:
    id: int
    author: int
    thread: int
    content: str
    timestamp: float