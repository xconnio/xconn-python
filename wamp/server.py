import aiohttp
from aiohttp import web

from wamp.router import Router
from wamp.wsacceptor import AIOHttpAcceptor


class Server:
    def __init__(self, router: Router):
        self.router = router

    async def _websocket_handler(self, request):
        ws = web.WebSocketResponse(protocols=["wamp.2.json", "wamp.2.cbor", "wamp.2.msgpack"])
        # upgrade this connection to websocket.
        await ws.prepare(request)

        acceptor = AIOHttpAcceptor()
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

    def start(self, host: str, port: int):
        app = web.Application()
        app.router.add_get("/ws", self._websocket_handler)
        web.run_app(app, host=host, port=port)
