from utils import db # BUG: LINUX SEGFAULT BECAUSE MARIADB CONNECTOR IS GAY

ssl = {
    'cert': './fullchain.pem',
    'key': './privkey.pem'
} # ADD YOUR SSL HERE

from sanic import Sanic
from sanic_ext import Extend


# TODO: REMOVE, PRE BETA STUFF
from sanic.response import text
ACCESS_TOKENS = ["ACCESS_TOKENS"]

from json import loads
from asyncio import Queue

# BLUEPRINTS #
from blueprints.group import api

# UTILS #
from utils import redis, hashing, sse, cors

# Load configs
with open("server_data/origins.json", "r") as data:
    origins = loads(data.read())['list']

# Webserver
_app = Sanic("API")
_app.config.CORS_ORIGINS = origins
_app.config.FORWARDED_SECRET = "YOUR_SECRET" #TODO: do i even need this?

# Add OPTIONS handlers to any route that is missing it for CORS
_app.register_listener(cors.setup_options, "before_server_start")


# Create DB, Redis, Hasher, SSE Object
_db = db.DB(db.mariadb_pool(0)) # Create the connection to the DB
_redis = redis.RDB
_hasher = hashing.Hasher()
_sse = sse.SSE(Queue(), _db)
_app.add_task(_sse.event_push_loop) # Make sure we run the event pusher, or nobody will be getting events

# Add all the blueprints

# Api (V1)
_app.blueprint(api)

# Inject everything needed.
@_app.on_request
async def setup_connection(request):
#    if "docs" in request.route.path:
#        pass
#    else:
#        if not request.headers.betatoken:
#                return text("Missing betatoken header")
#        if request.headers.betatoken not in ACCESS_TOKENS:
#                return text("You do not have access to this pre-beta API or your code is wrong.")
    request.ctx.db = _db
    request.ctx.redis = _redis
    request.ctx.hasher = _hasher
    request.ctx.sse = _sse

# Close the DB on exit
@_app.main_process_stop
async def close_db(app, loop):
    _db.pool.close()


if __name__ == '__main__':
    Extend(_app)
    _app.go_fast(host='localhost', port=42042,debug=False, access_log=True)
    #_app.go_fast(host='0.0.0.0', port=1234, debug=False, access_log=True)