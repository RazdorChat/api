from sanic import Blueprint

from blueprints.message import blueprint as message
from blueprints.nodes import blueprint as nodes
from blueprints.sse import blueprint as sse
from blueprints.user import blueprint as user

# All of the API
api = Blueprint.group(
    message,
    user,
    sse,
    nodes,
    # sse.blueprint,
    url_prefix="/api",
)
