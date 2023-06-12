from sanic import Sanic

# TODO: REMOVE, PRE BETA STUFF
from sanic.response import text
ACCESS_TOKENS = ["56748467863985672345467"]

from json import loads
from asyncio import Queue

# BLUEPRINTS #
from blueprints.group import api

# UTILS #
from utils import db, redis, hashing, sse, cors

# Load configs
with open("server_data/origins.json", "r") as data:
    origins = loads(data.read())['list']

# Webserver
_app = Sanic(__name__)

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
    if not request.headers.betatoken:
        return text("Missing betatoken header")
    if request.headers.betatoken not in ACCESS_TOKENS:
        return text("You do not have access to this pre-beta API or your code is wrong.")
    request.ctx.db = _db
    request.ctx.redis = _redis
    request.ctx.hasher = _hasher
    request.ctx.sse = _sse

# CORS
@_app.on_response
async def custom_banner(request, response):
    try:
        cors.add_cors_headers(request, response, origins)
    except Exception as e:
        print(e)
# Close the DB on exit
@_app.main_process_stop
async def close_db(app, loop):
    _db.pool.close()


async def main():
    server = await app.create_server(host='localhost', port=42042, debug=True, access_log=False, return_asyncio_server=True)
    if server is None:
        return

    await server.startup()
    await server.serve_forever()


if __name__ == '__main__':
    _app.go_fast(host='localhost', port=42042, debug=True, access_log=True)
    #try:
    #    set_event_loop(new_event_loop())
    #    run(main())
    #except KeyboardInterrupt:
    #    exit(0)