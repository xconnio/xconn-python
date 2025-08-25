import pathlib
import socket

import aiohttp
from aiohttp import web
from wampproto.auth import IServerAuthenticator

from xconn import helpers
from xconn.router import Router
from xconn.acceptor import AIOHttpAcceptor


class Server:
    def __init__(self, router: Router, authenticator: IServerAuthenticator = None):
        self.router = router
        self.authenticator = authenticator

    async def _websocket_handler(self, request):
        protocols = ["wamp.2.json", "wamp.2.cbor", "wamp.2.msgpack"]
        try:
            if helpers._CAPNP_AVAILABLE:
                protocols.append(helpers.CAPNPROTO_SUBPROTOCOL)
        except (ImportError, AttributeError):
            pass

        ws = web.WebSocketResponse(protocols=protocols)
        # upgrade this connection to websocket.
        await ws.prepare(request)

        try:
            acceptor = AIOHttpAcceptor(self.authenticator)
            base_session = await acceptor.accept(ws)
            self.router.attach_client(base_session)
        except Exception:
            await ws.close()

        while not ws.closed:
            msg = await ws.receive()

            if msg.type == aiohttp.WSMsgType.TEXT or msg.type == aiohttp.WSMsgType.BINARY:
                msg = base_session.serializer.deserialize(msg.data)
                await self.router.receive_message(base_session, msg)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                print(f"Error: {msg.exception()}")
            elif msg.type == aiohttp.WSMsgType.CLOSE:
                print("Client disconnected")
                break

        return ws

    async def start(self, host: str, port: int, start_loop: bool = False):
        print(f"starting server on {host}:{port}")
        app = web.Application()
        app.router.add_get("/ws", self._websocket_handler)

        if start_loop:
            web.run_app(app, host=host, port=port)
        else:
            runner = web.AppRunner(app)
            await runner.setup()

            site = aiohttp.web.TCPSite(runner, host=host, port=port)
            await site.start()

    async def start_unix_server(self, socket_path: str) -> None:
        if self._is_unix_socket_alive(socket_path):
            raise RuntimeError(f"Socket at {socket_path} is already in use")

        pathlib.Path(socket_path).unlink(missing_ok=True)

        print(f"Listening on unix://{socket_path}")

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(socket_path)
        sock.listen(128)
        sock.setblocking(False)

        app = web.Application()
        app.router.add_get("/", self._websocket_handler)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.SockSite(runner, sock)
        await site.start()

    def _is_unix_socket_alive(self, socket_path: str, timeout: float = 1.0) -> bool:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                sock.connect(socket_path)
            return True
        except (socket.error, ConnectionRefusedError):
            return False
