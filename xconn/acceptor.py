import socket
from typing import Sequence

from aiohttp import web
from wampproto import auth, acceptor, serializers, messages
from websockets import ServerProtocol
from websockets.sync.server import ServerConnection, Subprotocol

from xconn import types, helpers


class WebsocketsAcceptor:
    WSProtocols: Sequence[Subprotocol] = [
        Subprotocol("wamp.2.json"),
        Subprotocol("wamp.2.cbor"),
        Subprotocol("wamp.2.msgpack"),
    ]
    try:
        if helpers._CAPNP_AVAILABLE:
            WSProtocols.append(Subprotocol(helpers.CAPNPROTO_SUBPROTOCOL))
    except (ImportError, AttributeError):
        pass

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
                if a.is_aborted():
                    abort: messages.Abort = serializer.deserialize(to_send)
                    raise Exception(abort.reason)

                return types.BaseSession(ws, a.get_session_details(), serializer)


class AIOHttpAcceptor:
    def __init__(self, authenticator: auth.IServerAuthenticator = None) -> None:
        self.authenticator = authenticator

    async def accept(self, ws: web.WebSocketResponse) -> types.AIOHttpBaseSession:
        serializer = helpers.get_serializer(ws.ws_protocol)
        a = acceptor.Acceptor(serializer=serializer, authenticator=self.authenticator)

        if serializer is None or isinstance(serializer, serializers.JSONSerializer):
            send_func = ws.send_str
            receive_func = ws.receive_str
        else:
            send_func = ws.send_bytes
            receive_func = ws.receive_bytes

        while not ws.closed:
            msg = await receive_func()
            to_send, is_final = a.receive(msg)
            await send_func(to_send)
            if is_final:
                if a.is_aborted():
                    abort: messages.Abort = serializer.deserialize(to_send)
                    raise Exception(abort.reason)

                return types.AIOHttpBaseSession(ws, a.get_session_details(), serializer)
