from utils import db # BUG: LINUX SEGFAULT BECAUSE MARIADB CONNECTOR IS GAY

ssl = {
    'cert': './fullchain.pem',
    'key': './privkey.pem'
} # ADD YOUR SSL HERE

from sanic import Sanic
from sanic.response import html
from sanic_ext import Extend


from json import loads
from os import path, remove
from asyncio import Queue

# ERROR HANDLING #
import traceback
from datetime import datetime
from time import mktime
from sanic.response import HTTPResponse
from sanic.exceptions import NotFound



# BLUEPRINTS #
from blueprints.group import api

# UTILS #
from utils import redis, hashing, sse, cors, discord_legacy_webhook

# Make sure configs exist.
if not path.isfile("server_data/db.json") or not path.isfile("server_data/origins.json") or not path.isfile("server_data/config.json"):
    print("Please rename and fill out the example configs in server_data.")
    exit(0)

# Load configs
with open("server_data/origins.json", "r") as data:
    _origins = loads(data.read())['list']
with open("server_data/config.json", "r") as data:
    _config = loads(data.read())
with open("server_data/discord_legacy_webhooks.json", "r") as data:
    _discord_webhooks = loads(data.read()) # How ironic


# Validate configs / Check for first run
if path.isfile("FIRSTRUNDONTTOUCH"):
    try:
        input("FIRST RUN, VALIDATING CONFIGS: PRESS ENTER TO CONTINUE OR CRTL+C AND FILL THEM OUT IF YOU HAVNT FILLED THEM OUT.")
    except KeyboardInterrupt:
        exit(0)
    from jsonschema import validate
    from models.config import config, origins, webhooks
    for x in[(_config, config.schema), (origins, origins.schema)]: # This is bullshit, i know.
        try:
            validate(instance=x[0], schema=x[1])
        except:
            print("Exception validating config (JSON). Please check the configs.")
            exit(0)
    print("Validated files.")
    print("Removing first run file.")
    remove("FIRSTRUNDONTTOUCH")
    print("Starting...")


# Webserver
_app = Sanic("API")
_app.config.CORS_ORIGINS = _origins

# Add OPTIONS handlers to any route that is missing it for CORS
_app.register_listener(cors.setup_options, "before_server_start")


# Create DB, Redis, Hasher, SSE Object
_db = db.DB(db.mariadb_pool(0)) # Create the connection to the DB
_redis = redis.RDB
_hasher = hashing.Hasher()
_sse = sse.SSE(Queue(), _db)
_app.add_task(_sse.event_push_loop) # Make sure we run the event pusher, or nobody will be getting events
# NOTE: the python WS loop floors a single thread to 100% 24/7.

# Add all the blueprints

# Api (V1)
_app.blueprint(api)

# Error handler
@_app.exception(Exception)
async def catch_everything(request, exception):
    # TODO: work on this more, i dont know how sanic errors work and how to isinstance them
    if isinstance(exception, NotFound):
        return HTTPResponse("URL not found.", 404)
    unix_time = mktime(datetime.now().timetuple())
    _traceback = traceback.extract_tb(exception.__traceback__)
    with open(f"errors/{unix_time}.txt", "w+") as f:
        to_write = f"exception: {str(exception)}\ntraceback:\n{str(_traceback)}"
        if _discord_webhooks["enabled"] == True:
            webhook = discord_legacy_webhook.DiscordWebhook(_discord_webhooks["error"], "API Error")
            try:
                webhook.send(str(_traceback), str(exception))
            except Exception as e:
                to_write += f"\nwebhook: {str(e)}" # Probably a bad webhook
                # TODO: describe error more
        f.write(to_write)
        f.close()
    return HTTPResponse("Something happened internally, it has been reported and we will fix the error as soon as possible.", 500) 



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

if _config["api_landing_page"] == True:
    _temp = open(_config["api_landing_page_location"], "r") # TODO: check if exists
    landing_page = _temp.read()
    _temp.close()

    @_app.route("/")
    def index(request):
        return html(landing_page)
    

# Close the DB on exit
@_app.main_process_stop
async def close_db(app, loop):
    _db.pool.close()


if __name__ == '__main__':
    Extend(_app)
    _app.go_fast(host='localhost', port=42042,debug=False, access_log=True)
    #_app.go_fast(host='0.0.0.0', port=1234, debug=False, access_log=True)