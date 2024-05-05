from websockets.sync.client import connect
from wampproto import joiner, serializers, auth
from wampproto.joiner import Joiner

from xconn import types, helpers


class WebsocketsJoiner:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = None,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    def join(self, uri: str, realm: str) -> types.BaseSession:
        ws = connect(uri, subprotocols=[helpers.get_ws_subprotocol(serializer=self._serializer)])

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        ws.send(j.send_hello())

        while True:
            data = ws.recv()
            to_send = j.receive(data)
            if to_send is None:
                return types.BaseSession(ws, j.get_session_details(), self._serializer)

            ws.send(to_send)
