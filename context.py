class CustomContext(object):
    def __init__(self, db, redis, hasher, sse, secret):
        self.db = db
        self.redis = redis
        self.hasher = hasher
        self.internal_secret = secret
