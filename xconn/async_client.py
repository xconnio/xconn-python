from typing import Callable, Awaitable
from urllib.parse import urlparse

from wampproto import auth, serializers
from wampproto.auth import AnonymousAuthenticator

from xconn import types
from xconn.async_session import AsyncSession
from xconn.joiner import AsyncWebsocketsJoiner, AsyncRawSocketJoiner


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
