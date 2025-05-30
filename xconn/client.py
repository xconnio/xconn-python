from typing import Callable, Any, Awaitable

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
        self._on_connect_listeners: list[Callable[[Any], Any]] = []
        self._on_disconnect_listeners: list[Callable[[Any], Any]] = []

    def connect(self, url: str, realm: str) -> Session:
        j = WebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        details = j.join(url, realm)

        for connect_listener in self._on_connect_listeners:
            connect_listener()

        return Session(details, self._on_disconnect_listeners)

    def add_on_connect_listener(self, listener: Callable[[Any], Any]):
        self._on_connect_listeners.append(listener)

    def add_on_disconnect_listener(self, listener: Callable[[Any], Any]):
        self._on_disconnect_listeners.append(listener)


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
        self._on_connect_listeners: list[Callable[[Awaitable[Any]], Any]] = []
        self._on_disconnect_listeners: list[Callable[[Awaitable[Any]], Any]] = []

    async def connect(self, url: str, realm: str) -> AsyncSession:
        j = AsyncWebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        details = await j.join(url, realm)

        for connect_listener in self._on_connect_listeners:
            await connect_listener()

        return AsyncSession(details, self._on_disconnect_listeners)

    async def add_on_connect_listener(self, listener: Callable[[Awaitable[Any]], Any]):
        self._on_connect_listeners.append(listener)

    async def add_on_disconnect_listener(self, listener: Callable[[Awaitable[Any]], Any]):
        self._on_disconnect_listeners.append(listener)
