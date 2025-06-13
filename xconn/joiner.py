from wampproto import joiner, serializers, auth
from wampproto.joiner import Joiner

from xconn import types, helpers
from xconn.transports import WebSocketTransport, AsyncWebSocketTransport, RawSocketTransport, AsyncRawSocketTransport


class WebsocketsJoiner:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = None,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
        ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer
        self._ws_config = ws_config

    def join(self, uri: str, realm: str) -> types.BaseSession:
        transport = WebSocketTransport.connect(
            uri,
            subprotocols=[helpers.get_ws_subprotocol(serializer=self._serializer)],
            config=self._ws_config,
        )

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        transport.write(j.send_hello())

        while True:
            data = transport.read()
            to_send = j.receive(data)
            if to_send is None:
                return types.BaseSession(transport, j.get_session_details(), self._serializer)

            transport.write(to_send)


class AsyncWebsocketsJoiner:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = None,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
        ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    ):
        self._ws_config = ws_config
        self._authenticator = authenticator
        self._serializer = serializer

    async def join(self, uri: str, realm: str) -> types.AsyncBaseSession:
        transport = await AsyncWebSocketTransport.connect(
            uri,
            subprotocols=[helpers.get_ws_subprotocol(serializer=self._serializer)],
            config=self._ws_config,
        )

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        await transport.write(j.send_hello())

        while True:
            data = await transport.read()
            to_send = j.receive(data)
            if to_send is None:
                return types.AsyncBaseSession(transport, j.get_session_details(), self._serializer)

            await transport.write(to_send)


class RawSocketJoiner:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = None,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    def join(self, uri: str, realm: str) -> types.BaseSession:
        transport = RawSocketTransport.connect(uri, helpers.get_rs_protocol(self._serializer))

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        transport.write(j.send_hello())

        while True:
            data = transport.read()
            to_send = j.receive(data)
            if to_send is None:
                return types.BaseSession(transport, j.get_session_details(), self._serializer)

            transport.write(to_send)


class AsyncRawSocketJoiner:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = None,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    async def join(self, uri: str, realm: str) -> types.AsyncBaseSession:
        transport = await AsyncRawSocketTransport.connect(uri, helpers.get_rs_protocol(self._serializer))
        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        await transport.write(j.send_hello())

        while True:
            data = await transport.read()
            to_send = j.receive(data)
            if to_send is None:
                return types.AsyncBaseSession(transport, j.get_session_details(), self._serializer)

            await transport.write(to_send)
