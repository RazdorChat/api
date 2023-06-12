from dataclasses import dataclass

@dataclass
class User:
    id: int
    name: str
    authentication: None | str # Should only be None when not authenticated: ex requesting an endpoint that doesnt require auth
    salt: None | str # the same reasoning as above
    created_at: str | float