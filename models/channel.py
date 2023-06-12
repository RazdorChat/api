from dataclasses import dataclass
from typing import Optional

@dataclass
class Channel:
    guild_id: int
    old_guild_id: int
    id: int
    name: str
    delete_after_timeout: Optional[float]

@dataclass
class DMChannel:
    id: int