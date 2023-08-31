from utils.db import DBConnection
from utils.hashing import Hasher
from redis import Redis

class CustomContext(object):
    def __init__(self, db: DBConnection, redis: Redis, hasher: Hasher, secret: str):
        self.db = db
        self.redis = redis
        self.hasher = hasher
        self.internal_secret = secret
