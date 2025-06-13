from typing import Callable, Awaitable
from urllib.parse import urlparse

from wampproto import auth, serializers
from wampproto.auth import AnonymousAuthenticator

from xconn import types
from xconn.session import Session
from xconn.async_session import AsyncSession
from xconn.joiner import WebsocketsJoiner, AsyncWebsocketsJoiner, RawSocketJoiner, AsyncRawSocketJoiner


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

    def connect(
        self,
        uri: str,
        realm: str,
        connect_callback: Callable[[], None] | None = None,
        disconnect_callback: Callable[[], None] | None = None,
    ) -> Session:
        parsed = urlparse(uri)
        if parsed.scheme == "ws" or parsed.scheme == "wss" or parsed.scheme == "unix+ws":
            j = WebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        elif (
            parsed.scheme == "rs"
            or parsed.scheme == "rss"
            or parsed.scheme == "tcp"
            or parsed.scheme == "tcps"
            or parsed.scheme == "unix"
            or parsed.scheme == "unix+rs"
        ):
            j = RawSocketJoiner(self._authenticator, self._serializer)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        details = j.join(uri, realm)
        session = Session(details)

        session.on_disconnect(disconnect_callback)

        if connect_callback is not None:
            connect_callback()

        return session


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

    async def connect(
        self,
        uri: str,
        realm: str,
        connect_callback: Callable[[], Awaitable[None]] | None = None,
        disconnect_callback: Callable[[], Awaitable[None]] | None = None,
    ) -> AsyncSession:
        parsed = urlparse(uri)
        if parsed.scheme == "ws" or parsed.scheme == "wss":
            j = AsyncWebsocketsJoiner(self._authenticator, self._serializer, self._ws_config)
        elif (
            parsed.scheme == "rs"
            or parsed.scheme == "rss"
            or parsed.scheme == "tcp"
            or parsed.scheme == "tcps"
            or parsed.scheme == "unix"
            or parsed.scheme == "unix+rs"
        ):
            j = AsyncRawSocketJoiner(self._authenticator, self._serializer)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        details = await j.join(uri, realm)
        session = AsyncSession(details)

        session.on_disconnect(disconnect_callback)

        if connect_callback is not None:
            await connect_callback()

        return session
