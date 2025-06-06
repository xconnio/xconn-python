from websockets.sync.client import connect
from websockets.asyncio.client import connect as async_connect
from wampproto import joiner, serializers, auth
from wampproto.joiner import Joiner

from xconn import types, helpers


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
        ws = connect(
            uri,
            subprotocols=[helpers.get_ws_subprotocol(serializer=self._serializer)],
            open_timeout=self._ws_config.open_timeout,
            ping_interval=self._ws_config.ping_interval,
            ping_timeout=self._ws_config.ping_timeout,
            close_timeout=self._ws_config.close_timeout,
        )

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        ws.send(j.send_hello())

        while True:
            data = ws.recv()
            to_send = j.receive(data)
            if to_send is None:
                return types.BaseSession(ws, j.get_session_details(), self._serializer)

            ws.send(to_send)


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
        ws = await async_connect(
            uri,
            subprotocols=[helpers.get_ws_subprotocol(serializer=self._serializer)],
            open_timeout=self._ws_config.open_timeout,
            ping_interval=self._ws_config.ping_interval,
            ping_timeout=self._ws_config.ping_timeout,
            close_timeout=self._ws_config.close_timeout,
        )

        j: Joiner = joiner.Joiner(realm, serializer=self._serializer, authenticator=self._authenticator)
        await ws.send(j.send_hello())

        while True:
            data = await ws.recv()
            to_send = j.receive(data)
            if to_send is None:
                return types.AsyncBaseSession(ws, j.get_session_details(), self._serializer)

            await ws.send(to_send)
