from dataclasses import dataclass

@dataclass
class Void:
    op = "void"

@dataclass
class MissingJson:
    op = "Missing JSON."

@dataclass
class MissingRequiredJson:
    op = "Missing required JSON keys."

@dataclass
class Unauthorized:
    op = "Unauthorized."

@dataclass
class Deleted:
    op = "Deleted."

@dataclass
class Sent:
    op = "Sent."

@dataclass
class Done:
    op = "Done."

@dataclass
class AlreadyAdded:
    op = "Already added."



@dataclass
class UserCreated:
    op = "Created."
    id: int

@dataclass
class UserAuthkeyCreated:
    op = "Created."
    authentication: str
    id: int



@dataclass
class Relationship:
    id: int
    type: str

