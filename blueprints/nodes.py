from sanic.blueprints import Blueprint
from sanic.response import json
from sanic_ext import openapi

from models import ops
from utils import checks

from sanic.request import Request
from sanic.response import JSONResponse

# Create the main blueprint to work with
blueprint = Blueprint("Node", url_prefix="/nodes")


@blueprint.post("/ws/register", strict_slashes=True)
@openapi.exclude()
@openapi.response(200, {"application/json": {"op": "Added"}})
@openapi.response(400, {"application/json": ops.MissingJson})
@openapi.response(400, {"application/json": ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
async def register_ws_node(request: Request) -> JSONResponse:
    """Registers a new node to the network.

    Args:
        request (Request): The request that caused the exception.

    Returns:
        JSONResponse: The response to send to the client.
    """
    data = request.json
    if not data:
        return json({"op": ops.MissingJson})

    if not all(k in data for k in ("id", "name", "addr", "port", "secret", "hostname")):
        return json({"op": ops.MissingRequiredJson.op})
    
    if not checks.matches_internal_secret(data["secret"], request.app.ctx.internal_secret):
        return json({"op": ops.Unauthorized.op})

    if not request.app.ctx.redis.get(f"nodes:{data['id']}"):
        request.app.ctx.redis.set(f"nodes:{data['id']}", f"{data['addr']}:{data['port']}")
        request.app.ctx.redis.set(f"nodes:available:{data['id']}", f"{data['hostname']}")

    return json({"op": "Added"}, status=200)


@blueprint.post("/ws/unregister", strict_slashes=True)
@openapi.exclude()
@openapi.response(200, {"application/json": {"op": "Removed"}})
@openapi.response(400, {"application/json": ops.MissingJson})
@openapi.response(400, {"application/json": ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
async def unregister_ws_node(request: Request) -> JSONResponse:
    """Unregisters a node from the network.

    Args:
        request (Request): The request that caused the exception.

    Returns:
        JSONResponse: The response to send to the client.
    """
    data = request.json
    if not data:
        return json({"op": ops.MissingJson})

    if not all(k in data for k in ("id", "secret")):
        return json({"op": ops.MissingRequiredJson.op})

    if not checks.matches_internal_secret(data["secret"], request.app.ctx.internal_secret):
        return json({"op": ops.Unauthorized.op})

    result = request.app.ctx.redis.get(f"nodes:{data['id']}")

    if result != None:
        keys = []
        keys.extend(request.app.ctx.redis.keys(f"nodes:{data['id']}"))
        keys.extend(request.app.ctx.redis.keys(f"nodes:available:{data['id']}"))

        request.app.ctx.redis.delete(*keys)

    return json({"op": "Removed"}, status=200)


@blueprint.post("/ws/update", strict_slashes=True)
@openapi.exclude()
@openapi.response(200, {"application/json": {"op": "Removed"}})
@openapi.response(400, {"application/json": ops.MissingJson})
@openapi.response(400, {"application/json": ops.MissingRequiredJson})
@openapi.response(401, {"application/json" : ops.Unauthorized})
async def update_ws_node(request: Request) -> JSONResponse:
    """Updates a node in the network.

    Args:
        request (Request): The request that caused the exception.

    Returns:
        JSONResponse: The response to send to the client.
    """
    data = request.json
    if not data:
        return json({"op": ops.MissingJson})

    if not all(k in data for k in ("id", "secret")):
        return json({"op": ops.MissingRequiredJson.op})

    if not checks.matches_internal_secret(data["secret"], request.app.ctx.internal_secret):
        return json({"op": ops.Unauthorized.op})

    if request.app.ctx.redis.get(f"nodes:{data['id']}") != None:
        request.app.ctx.redis.delete(request.app.ctx.redis.keys(f"nodes:available:{data['id']}"))

    return json({"op": "Removed from available nodes"}, status=200)


@blueprint.get("/ws/nodes", strict_slashes=True)
@openapi.description("Gets availible WS nodes. Returns a list of ip:ports you can connect to.")
@openapi.response(200, {"application/json": {"op": list[str]}})
@openapi.response(200, {"application/json": {"op": str}})
@openapi.response(200, {"application/json": {"op": ops.Void.op}})
# @openapi.response(401, {"application/json" : ops.Unauthorized})
async def get_ws_nodes(request: Request) -> JSONResponse:
    """Gets all nodes in the network.

    Args:
                request (Request): The request that caused the exception.

    Returns:
                JSONResponse: The response to send to the client.
    """
    _temp = request.app.ctx.redis.keys("nodes:available:*")
    if _temp == None or len(_temp) == 0:
        return json({"op": ops.Void.op}, status=200)

    result = request.app.ctx.redis.mget(*_temp)

    return json({"op": result}, status=200)
