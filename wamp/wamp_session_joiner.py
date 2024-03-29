from simple_websocket import Client
from wampproto import joiner, serializers, auth


class WAMPSessionJoiner:
    JSON_SUBPROTOCOL = "wamp.2.json"
    CBOR_SUBPROTOCOL = "wamp.2.cbor"
    MSGPACK_SUBPROTOCOL = "wamp.2.msgpack"

    def __init__(
        self,
        authenticator: auth.IClientAuthenticator,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    def get_subprotocol(self, serializer: serializers.Serializer):
        if isinstance(serializer, serializers.JSONSerializer):
            return WAMPSessionJoiner.JSON_SUBPROTOCOL
        elif isinstance(serializer, serializers.CBORSerializer):
            return WAMPSessionJoiner.CBOR_SUBPROTOCOL
        elif isinstance(serializer, serializers.MsgPackSerializer):
            return WAMPSessionJoiner.MSGPACK_SUBPROTOCOL
        else:
            raise ValueError("invalid serializer")

    def join(self, uri: str, realm: str):
        ws = Client.connect(uri, subprotocols=self.get_subprotocol(serializer=self._serializer))

        j = joiner.Joiner(realm, serializer=self._serializer)
        ws.send(j.send_hello())

        while True:
            data = ws.receive()
            to_send = j.receive(data)
            if to_send is None:
                return j.get_session_details()

            ws.send(to_send)
