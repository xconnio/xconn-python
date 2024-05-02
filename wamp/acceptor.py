import socket
from typing import Sequence

from aiohttp import web
from wampproto import auth, acceptor
from websockets import ServerProtocol
from websockets.sync.server import ServerConnection, Subprotocol

from wamp import types, helpers


class WebsocketsAcceptor:
    WSProtocols: Sequence[Subprotocol] = [
        Subprotocol("wamp.2.json"),
        Subprotocol("wamp.2.cbor"),
        Subprotocol("wamp.2.msgpack"),
    ]

    def __init__(self, authenticator: auth.IServerAuthenticator = None) -> None:
        self.authenticator = authenticator
        self.subprotocols = WebsocketsAcceptor.WSProtocols

    def accept(self, conn: socket.socket) -> types.BaseSession:
        ws = ServerConnection(conn, ServerProtocol(subprotocols=WebsocketsAcceptor.WSProtocols))
        ws.handshake()

        serializer = helpers.get_serializer(ws.subprotocol)
        a = acceptor.Acceptor(serializer=serializer, authenticator=self.authenticator)

        while True:
            data = ws.recv()
            to_send, is_final = a.receive(data)
            ws.send(to_send)
            if is_final:
                return types.BaseSession(ws, a.get_session_details(), serializer)


class AIOHttpAcceptor:
    def __init__(self, authenticator: auth.IServerAuthenticator = None) -> None:
        self.authenticator = authenticator

    async def accept(self, ws: web.WebSocketResponse) -> types.AIOHttpBaseSession:
        serializer = helpers.get_serializer(ws.ws_protocol)
        a = acceptor.Acceptor(serializer=serializer, authenticator=self.authenticator)

        while not ws.closed:
            msg = await ws.receive()
            to_send, is_final = a.receive(msg.data)
            await ws.send_bytes(to_send)
            if is_final:
                return types.AIOHttpBaseSession(ws, a.get_session_details(), serializer)
