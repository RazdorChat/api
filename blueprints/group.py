from sanic import Blueprint

# Bits of the API
from blueprints.user import blueprint as user
from blueprints.message import blueprint as message
from blueprints.sse import blueprint as sse
from blueprints.nodes import blueprint as nodes




# All of the API
api = Blueprint.group(message,
					  user,
					  sse,
					  nodes,
					  #sse.blueprint,
					  url_prefix="/api")