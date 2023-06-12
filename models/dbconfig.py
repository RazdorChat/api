from dataclasses import dataclass

@dataclass
class DBConfig:
    host = 'localhost'
    port = 3306
    user: str
    password: str
    database: str
    pool_size = 20