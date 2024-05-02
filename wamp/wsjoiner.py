from simple_websocket import Client
from wampproto import joiner, serializers, auth
from wampproto.joiner import Joiner

from wamp import types, helpers


class WAMPSessionJoiner:

    def __init__(
        self,
        authenticator: auth.IClientAuthenticator,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    def join(self, uri: str, realm: str) -> types.BaseSession:
        ws = Client.connect(uri, subprotocols=helpers.get_ws_subprotocol(serializer=self._serializer))

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer)
        ws.send(j.send_hello())

        while True:
            data = ws.receive()
            to_send = j.receive(data)
            if to_send is None:
                return types.BaseSession(ws, j.get_session_details(), self._serializer)

            ws.send(to_send)
