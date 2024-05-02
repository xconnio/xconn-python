import argparse
import importlib

import uvloop

from wamp.app import WampApp
from wamp.router import Router
from wamp.server import Server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("APP")

    parsed = parser.parse_args()

    split = parsed.APP.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    module = importlib.import_module(split[0])
    app: WampApp = getattr(module, split[1])
    if not isinstance(app, WampApp):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    # uvloop makes things fast.
    uvloop.install()

    r = Router()
    r.add_realm("realm1")

    # FIXME: attach a local client to the router and register
    #  all procedures from the app.
    for procedure, handler in app.procedures.items():
        pass

    server = Server(r)
    server.start(parsed.host, parsed.port)
