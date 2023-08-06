from __future__ import annotations

from collections import defaultdict
from typing import Dict, FrozenSet, Iterable

from sanic import response
from sanic.router import Route


def _add_cors_headers(
    response: response.HTTPResponse, methods: Iterable[str], origins: str | bool = None
) -> None:  # This is on startup to enable OPTIONS requests.
    """Adds CORS headers to a response.

    Args:
                response (response.HTTPResponse): The response to add the headers to.
                methods (Iterable[str]): The methods to allow.
                origins (str | bool, optional): The origins to allow. Defaults to None.
    """
    allow_methods = list(set(methods))
    headers = {
        "Access-Control-Allow-Methods": ",".join(allow_methods),
        "Access-Control-Allow-Origin": "".join(origins) if origins else "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": ("origin, content-type, " "authorization"),
    }
    response.headers.extend(headers)


def add_cors_headers(request: response.HTTPRequest, response: response.HTTPResponse, origins: list = None):
    """Adds CORS headers to a response if the request is not an OPTIONS request.

    Args:
            request (response.HTTPRequest): The request to check.
            response (response.HTTPResponse): The response to add the headers to.
            origins (list, optional): The origins to allow. Defaults to None.
    """
    if request.method != "OPTIONS":
        methods = [method for method in request.route.methods]
        _add_cors_headers(response, methods, origins)


def _compile_routes_needing_options(routes: Dict[str, Route]) -> Dict[str, FrozenSet]:
    """Compiles a list of routes that need OPTIONS handlers.

    Args:
            routes (Dict[str, Route]): The routes to check.

    Returns:
            Dict[str, FrozenSet]: The routes that need OPTIONS handlers.
    """
    needs_options = defaultdict(list)
    # This is 21.12 and later. You will need to change this for older versions.
    for route in routes.values():
        if "OPTIONS" not in route.methods:
            needs_options[route.uri].extend(route.methods)

    return {uri: frozenset(methods) for uri, methods in dict(needs_options).items()}


def _options_wrapper(handler: callable, methods: Iterable[str]) -> callable:
    """Wraps a handler to add CORS headers.

    Args:
            handler (function): The handler to wrap.
                    methods (Iterable[str]): The methods to allow.

    Returns:
            function: The wrapped handler.
    """

    def wrapped_handler(request, *args, **kwargs):
        nonlocal methods
        return handler(request, methods)

    return wrapped_handler


async def options_handler(request: response.HTTPRequest, methods: Iterable[str]) -> response.HTTPResponse:
    """Handles OPTIONS requests.

    Args:
            request (response.HTTPRequest): The request to handle.
            methods (Iterable[str]): The methods to allow.

    Returns:
            response.HTTPResponse: The response.
    """
    resp = response.empty()
    allow_methods = list(set(methods))
    if "OPTIONS" not in allow_methods:
        allow_methods.append("OPTIONS")
    _add_cors_headers(resp, methods)
    return resp


def setup_options(app, _):
    """Sets up OPTIONS handlers for CORS.

    Args:
        app (sanic.Sanic): The app to set up.

    """
    app.router.reset()
    needs_options = _compile_routes_needing_options(app.router.routes_all)
    for uri, methods in needs_options.items():
        app.add_route(
            _options_wrapper(options_handler, methods),
            uri,
            methods=["OPTIONS"],
        )
    app.router.finalize()
