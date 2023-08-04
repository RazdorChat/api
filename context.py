

class CustomContext:
	def __init__(self, db, redis, hasher, sse):
		self.db = db
		self.redis = redis
		self.hasher = hasher
		self.sse = sse

