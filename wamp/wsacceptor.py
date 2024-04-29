import socket
from typing import Sequence

from wampproto import auth, acceptor
from websockets import ServerProtocol
from websockets.sync.server import ServerConnection, Subprotocol

from wamp import types, helpers


class WAMPSessionAcceptor:
    WSProtocols: Sequence[Subprotocol] = [
        Subprotocol("wamp.2.json"),
        Subprotocol("wamp.2.cbor"),
        Subprotocol("wamp.2.msgpack"),
    ]

    def __init__(
        self, authenticator: auth.IServerAuthenticator = None, subprotocols: Sequence[Subprotocol] = None
    ) -> None:
        self.authenticator = authenticator
        if subprotocols is None:
            self.subprotocols = WAMPSessionAcceptor.WSProtocols
        else:
            self.subprotocols = subprotocols

    def accept(self, conn: socket.socket) -> types.BaseSession:
        ws = ServerConnection(conn, ServerProtocol(subprotocols=WAMPSessionAcceptor.WSProtocols))
        ws.handshake()

        serializer = helpers.get_serializer(ws.subprotocol)
        a = acceptor.Acceptor(serializer=serializer, authenticator=self.authenticator)

        while True:
            data = ws.recv()
            to_send, is_final = a.receive(data)
            ws.send(to_send)
            if is_final:
                return types.BaseSession(ws, a.get_session_details(), serializer)
