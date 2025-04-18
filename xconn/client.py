from wampproto import auth, serializers
from wampproto.auth import AnonymousAuthenticator

from xconn import types
from xconn.session import Session
from xconn.async_session import AsyncSession
from xconn.joiner import WebsocketsJoiner, AsyncWebsocketsJoiner


class Client:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = AnonymousAuthenticator(""),
        serializer: serializers.Serializer = serializers.JSONSerializer(),
        ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer
        self._ws_config = ws_config

    def connect(self, url: str, realm: str) -> Session:
        j = WebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        details = j.join(url, realm)

        return Session(details)


class AsyncClient:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = AnonymousAuthenticator(""),
        serializer: serializers.Serializer = serializers.JSONSerializer(),
        ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer
        self._ws_config = ws_config

    async def connect(self, url: str, realm: str) -> AsyncSession:
        j = AsyncWebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        details = await j.join(url, realm)

        return AsyncSession(details)
