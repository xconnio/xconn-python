from wampproto.joiner import Joiner, serializers, auth


class WAMPSessionJoiner:
    JSON_SUBPROTOCOL = "wamp.2.json"
    CBOR_SUBPROTOCOL = "wamp.2.cbor"
    MSGPACK_SUBPROTOCOL = "wamp.2.msgpack"

    def __init__(
        self,
        socket,
        authenticator: auth.IClientAuthenticator,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._socket = socket
        self._authenticator = authenticator
        self._serializer = serializer

    def get_subprotocol(self, serializer: serializers.Serializer):
        if isinstance(serializer, serializers.JSONSerializer):
            return self.JSON_SUBPROTOCOL
        elif isinstance(serializer, serializers.CBORSerializer):
            return self.CBOR_SUBPROTOCOL
        elif isinstance(serializer, serializers.MsgPackSerializer):
            return self.MSGPACK_SUBPROTOCOL
        else:
            raise ValueError("invalid serializer")

    def join(self, uri: str, realm: str):
        self._socket.connect(uri, subprotocol=self.get_subprotocol(serializer=self._serializer))

        j = Joiner(realm, serializer=self._serializer)
        self._socket.send(j.send_hello())

        while True:
            data = self._socket.receive()
            to_send = j.receive(data)
            if to_send is None:
                return j.get_session_details()

            self._socket.send(to_send)
