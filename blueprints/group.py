from sanic import Blueprint

# Bits of the API
from blueprints.user import blueprint as user
from blueprints.message import blueprint as message
from blueprints.sse import blueprint as sse
from blueprints.channel import blueprint as channel



# All of the API
api = Blueprint.group(message,
                      user,
                      sse,
                      channel,
                      #sse.blueprint,
                      url_prefix="/api")