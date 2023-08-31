from utils import db # BUG: LINUX SEGFAULT BECAUSE MARIADB CONNECTOR IS GAY

import logging
import traceback
import context as context  # Custom Context class

from asyncio import Queue
from datetime import datetime
from json import loads
from os import path, remove
from time import mktime
from typing import TYPE_CHECKING

from sanic import Sanic
from sanic.exceptions import NotFound, SanicException, InvalidUsage
from sanic.response import HTTPResponse, html
from sanic.request import Request
from sanic_ext import Extend

from blueprints.group import api
from utils import (
    cors,
    discord_legacy_webhook,
    hashing,
    redis,
    id_generator
)
from utils.args_utils import parse_args
from utils.logging_utils import setup_logger

logger = logging.getLogger(__name__)

LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "": {
            "level": "ERROR",  # Disable needless sanic prints, keeping only errors.
        }
    },
}


# Make sure configs exist.
if not path.isfile("server_data/db.json") or not path.isfile("server_data/origins.json") or not path.isfile("server_data/config.json"):
    logger.critical("Please rename and fill out the example configs in server_data.")
    exit(0)

# Load configs
with open("server_data/origins.json", "r") as data:
    _origins = loads(data.read())["list"]
with open("server_data/config.json", "r") as data:
    _config = loads(data.read())
with open("server_data/discord_legacy_webhooks.json", "r") as data:
    _discord_webhooks = loads(data.read())  # How ironic


# Validate configs
def pre_run_validation() -> bool:
    from jsonschema import validate

    from models.config import config, origins

    for x in [(_config, config.schema), (origins, origins.schema)]:
        try:
            validate(instance=x[0], schema=x[1])
        except:
            logger.info("Exception validating config (JSON). Please check the configs.")
            return False

    return True


# Webserver
_app = Sanic("API", log_config=LOG_CONFIG)

_app.config.CORS_ORIGINS = _origins

# Add OPTIONS handlers to any route that is missing it for CORS
_app.register_listener(cors.setup_options, "before_server_start")


# Create DB, Redis, Hasher, Secret, Log file and Context
try:
    _db = db.DB(db.mariadb_pool(0))  # Create the connection to the DB
except db.mariadb.OperationalError:
    logger.critical("Error connecting to DB, exiting...")
    exit(0)
    
_redis = redis.RDB
_hasher = hashing.Hasher()
_secret = id_generator.generate_secret()
log_file = open(f"errors/{mktime(datetime.now().timetuple())}.txt", "a+")
_app.ctx = context.CustomContext(_db, _redis, _hasher, _secret)

# Write secret if python-ws is enabled.
if _config["py_ws_drag_n_drop"] == True:
    logger.info("Python WS enabled, assuming correct setup and generating secret.txt")
    with open("ws/secret.txt", "w+") as f:
        f.write(_secret)
        f.close()
    logger.info("You can now start the WS server at any time.\n")

_app.blueprint(api)


if _config["api_landing_page"] == True:
    _temp = open(_config["api_landing_page_location"], "r")  # TODO: check if exists
    landing_page = html(_temp.read())
    _temp.close()
    del _temp

    @_app.route("/")
    def index(request: Request):
        return landing_page

    # TODO: when webapp is finished, redirect to webapp subdomain.


@_app.after_server_start
async def start(app: Sanic, loop):
    """Starts all needed tasks.

    Args:
            app (sanic.Sanic): The app to start the task on.
            loop (asyncio.AbstractEventLoop): The event loop to use.
    """
    logger.info("WS Tasks...")
    app.add_task(redis.prune_offline_nodes) # Remove offline nodes automatically.
    logger.info("-----    STARTED    -----")
    logger.debug(f"Running @ {_config['host']}:{_config['port']}")


# Error handler
@_app.exception(Exception)
async def catch_everything(request: Request, exception: Exception) -> HTTPResponse:
    """Catches all exceptions and logs them.

    Args:
            request (sanic.request.Request): The request that caused the exception.
            exception (Exception): The exception that was raised.

    Returns:
            HTTPResponse: The response to send to the client.

    """
    # TODO: work on this more, i dont know how sanic errors work and how to isinstance them
    if isinstance(exception, NotFound):
        return HTTPResponse("URL not found.", 404)
    elif isinstance(exception, InvalidUsage):
        return HTTPResponse("Invalid usage. Refer to the Documentation for the correct methods to use on URLs, POSTs cannot be sent to GET endpoints, and so on.")
    _traceback = traceback.extract_tb(exception.__traceback__)
    to_write = f"exception: {str(exception)}\ntraceback:\n{str(_traceback)}"
    if _discord_webhooks["enabled"] == True:
        webhook = discord_legacy_webhook.DiscordWebhook(_discord_webhooks["error"], "API Error")
        try:
            webhook.send(str(_traceback), str(exception))
        except Exception as e:
            to_write += f"\nwebhook: {str(e)}"  # Probably a bad webhook
            # TODO: describe error more
    log_file.write(to_write)
    logger.error(to_write)
    return HTTPResponse("Something happened internally, it has been reported and we will fix the error as soon as possible.", 500)


# Close the DB on exit
@_app.main_process_stop
async def close(app: Sanic, loop):
    """Closes the DB connection and kills the SSE task.

    Args:
        app (sanic.Sanic): The app to close the task on.

    """
    logger.info("-----    EXITING    -----")
    logger.info("Closing DB connection...")
    _db.pool.close()
    logger.info("Closing log file...")
    log_file.close()
    logger.info("Done.")


def main():
    try:
        logger.info("-----    STARTING    -----")
        Extend(_app)
        _app.run(
            host=_config["host"], port=_config["port"], debug=False, access_log=False, motd=_config["selfhosting"]
        )  # Disable MOTD in prod.
    except KeyboardInterrupt:
        logger.critical("Force exited, this may have messed something up.")


if __name__ == "__main__":
    if pre_run_validation() == True:
        logger.info("Validated configs.")
        logger.info("Starting...")
        args = parse_args()
        setup_logger(level=args.log_level, stream_logs=args.console_log)
        main()
    else:
        exit(0)
