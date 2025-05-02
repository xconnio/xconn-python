import argparse
import asyncio
import importlib
import sys

import uvloop
from wampproto.serializers import CBORSerializer

from xconn.app import App
from xconn.router import Router
from xconn.server import Server
from xconn.async_session import AsyncSession
from xconn.types import ServerSideLocalBaseSession, ClientSideLocalBaseSession
from xconn._client.cli import add_client_subparser
from xconn._router.cli import add_router_subparser


def main2():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--realm", type=str, default="realm1")
    parser.add_argument("--directory", type=str, default=".")
    parser.add_argument("APP")

    parsed = parser.parse_args()

    split = parsed.APP.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    # TODO: find a better, reliable way
    sys.path.append(parsed.directory)
    module = importlib.import_module(split[0])
    app: App = getattr(module, split[1])
    if not isinstance(app, App):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    # uvloop makes things fast.
    uvloop.install()

    router = Router()
    router.add_realm(parsed.realm)

    serializer = CBORSerializer()
    client_side_base = ClientSideLocalBaseSession(1, parsed.realm, "local", "local", serializer, router)
    server_side_base = ServerSideLocalBaseSession(1, parsed.realm, "local", "local", serializer)
    server_side_base.set_other(client_side_base)

    router.attach_client(server_side_base)

    async def setup():
        session = AsyncSession(client_side_base)
        for procedure, handler in app.procedures.items():
            await session.register(procedure, handler)
            print(f"registered procedure {procedure}")

        server = Server(router)
        await server.start(parsed.host, parsed.port, start_loop=False)
        print(f"Listening for websocket connections on ws://{parsed.host}:{parsed.port}/ws")
        await asyncio.Event().wait()

    try:
        asyncio.run(setup())
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser(description="XConn CLI")
    subparsers = parser.add_subparsers(dest="component")

    # Add subcommands from other modules
    add_client_subparser(subparsers)
    add_router_subparser(subparsers)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    elif hasattr(args, "print_help"):
        args.print_help()
    else:
        parser.print_help()
