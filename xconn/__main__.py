import asyncio
import argparse
import importlib
import sys

import uvloop
from wampproto.serializers import CBORSerializer

from xconn.app import XConnApp
from xconn.router import Router
from xconn.server import Server
from xconn.session import AsyncSession
from xconn.types import ServerSideLocalBaseSession, ClientSideLocalBaseSession


def main():
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
    app: XConnApp = getattr(module, split[1])
    if not isinstance(app, XConnApp):
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


if __name__ == "__main__":
    main()
