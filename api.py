import context # Custom Context class

from utils import db # BUG: LINUX SEGFAULT BECAUSE MARIADB CONNECTOR IS GAY

ssl = {
	'cert': './fullchain.pem',
	'key': './privkey.pem'
} # ADD YOUR SSL HERE

from sanic import Sanic
from sanic.response import html
from sanic_ext import Extend
from sanic.exceptions import SanicException

from json import loads
from os import path, remove
from asyncio import Queue

# ERROR HANDLING / LOGGING #
import traceback
import logging.config
from datetime import datetime
from time import mktime
from sanic.response import HTTPResponse
from sanic.exceptions import NotFound

LOG_CONFIG = {
	'version': 1,
	'disable_existing_loggers': False,
	'loggers': {
		'': {
			'level': 'ERROR', # Disable needless sanic prints, keeping only errors.
		}
	}
}



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
	from models.config import config, origins
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
_app = Sanic("API", log_config=LOG_CONFIG)

_app.config.CORS_ORIGINS = _origins

# Add OPTIONS handlers to any route that is missing it for CORS
_app.register_listener(cors.setup_options, "before_server_start")


# Create DB, Redis, Hasher, SSE, Log file and nodes Object
try:
	_db = db.DB(db.mariadb_pool(0)) # Create the connection to the DB
except db.mariadb.OperationalError:
	print("Error connecting to DB, exiting...")
	exit(0)
_redis = redis.RDB
_hasher = hashing.Hasher()
_sse = sse.SSE(Queue(), _db)
log_file = open(f"errors/{mktime(datetime.now().timetuple())}.txt", 'a+')

_app.ctx = context.CustomContext(_db, _redis, _hasher, _sse)


@_app.after_server_start
async def start(app, loop):
	print("Starting SSE task...")
	app.add_task(_sse.event_push_loop, name="sse_loop") # Make sure we run the event pusher, or nobody will be getting events
	app.add_task(redis.prune_offline_nodes, name="ws_prune_loop") # Make sure we run the event pusher, or nobody will be getting events
	# NOTE: the python WS loop floors a single thread to 100% 24/7.
	# NOTE: may have been fixed with by not using no_wait in queue
	print("Started SSE task.")
	print("\n-----    STARTED    -----\n")
	print(f"Running @ {_config['host']}:{_config['port']}")


# Add all the blueprints

# Api (V1)
_app.blueprint(api)

# Error handler
@_app.exception(Exception)
async def catch_everything(request, exception):
	# TODO: work on this more, i dont know how sanic errors work and how to isinstance them
	if isinstance(exception, NotFound):
		return HTTPResponse("URL not found.", 404)
	_traceback = traceback.extract_tb(exception.__traceback__)
	to_write = f"exception: {str(exception)}\ntraceback:\n{str(_traceback)}"
	if _discord_webhooks["enabled"] == True:
		webhook = discord_legacy_webhook.DiscordWebhook(_discord_webhooks["error"], "API Error")
		try:
			webhook.send(str(_traceback), str(exception))
		except Exception as e:
			to_write += f"\nwebhook: {str(e)}" # Probably a bad webhook
			# TODO: describe error more
	log_file.write(to_write)
	print(to_write)
	del to_write, _traceback, webhook
	return HTTPResponse("Something happened internally, it has been reported and we will fix the error as soon as possible.", 500)

# Serve the landing page
if _config["api_landing_page"] == True:
	_temp = open(_config["api_landing_page_location"], "r") # TODO: check if exists
	landing_page = _temp.read()
	_temp.close()
	del _temp

	@_app.route("/")
	def index(request):
		return html(landing_page)

	# TODO: when webapp is finished, redirect to webapp subdomain.


# Close the DB on exit
@_app.main_process_stop
async def close(app, loop):
	print("-----    EXITING    -----")
	print("Closing DB connection...")
	_db.pool.close()
	try:
		print("Killing SSE task...")
		await app.cancel_task("sse_loop")
	except SanicException: # Task already killed
		pass
	print("Closing log file...")
	log_file.close()
	print("Done.")

try:
	if __name__ == '__main__':
		print("-----    STARTING    -----")
		if _config["py_ws_drag_n_drop"] == True:
			print("\nPython WS enabled, assuming correct setup and generating secret.txt")
			import secrets
			with open("ws/secret.txt", "w+") as f:
				f.write(secrets.token_urlsafe(64))
				f.close()
			del secrets
			print("You can now start the WS server at any time.\n")
		Extend(_app)
		_app.run(host=_config["host"], port=_config["port"],debug=False, access_log=False, motd=_config["selfhosting"]) # Disable MOTD in prod.
except KeyboardInterrupt:
	print("Force exited, this may have messed something up.")
