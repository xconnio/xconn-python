import aiohttp
from aiohttp import web
from wampproto.auth import IServerAuthenticator

from xconn.router import Router
from xconn.acceptor import AIOHttpAcceptor


class Server:
    def __init__(self, router: Router, authenticator: IServerAuthenticator = None):
        self.router = router
        self.authenticator = authenticator

    async def _websocket_handler(self, request):
        ws = web.WebSocketResponse(protocols=["wamp.2.json", "wamp.2.cbor", "wamp.2.msgpack"])
        # upgrade this connection to websocket.
        await ws.prepare(request)

        acceptor = AIOHttpAcceptor(self.authenticator)
        base_session = await acceptor.accept(ws)
        self.router.attach_client(base_session)

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
        app = web.Application()
        app.router.add_get("/ws", self._websocket_handler)

        if start_loop:
            web.run_app(app, host=host, port=port)
        else:
            runner = web.AppRunner(app)
            await runner.setup()

            site = aiohttp.web.TCPSite(runner, host=host, port=port)
            await site.start()
