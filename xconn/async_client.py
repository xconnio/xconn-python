from typing import Callable, Awaitable
from urllib.parse import urlparse

from wampproto import auth, serializers

from xconn import types
from xconn.async_session import AsyncSession
from xconn.joiner import AsyncWebsocketsJoiner, AsyncRawSocketJoiner


class AsyncClient:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = auth.AnonymousAuthenticator(""),
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
        return await connect(
            uri, realm, self._authenticator, self._serializer, self._ws_config, connect_callback, disconnect_callback
        )


async def connect(
    uri: str,
    realm: str,
    authenticator: auth.IClientAuthenticator = None,
    serializer: serializers.Serializer = serializers.CBORSerializer(),
    ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    connect_callback: Callable[[], Awaitable[None]] | None = None,
    disconnect_callback: Callable[[], Awaitable[None]] | None = None,
) -> AsyncSession:
    parsed = urlparse(uri)
    if parsed.scheme == "ws" or parsed.scheme == "wss":
        j = AsyncWebsocketsJoiner(authenticator, serializer, ws_config)
    elif (
        parsed.scheme == "rs"
        or parsed.scheme == "rss"
        or parsed.scheme == "tcp"
        or parsed.scheme == "tcps"
        or parsed.scheme == "unix"
        or parsed.scheme == "unix+rs"
    ):
        j = AsyncRawSocketJoiner(authenticator, serializer)
    else:
        raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

    details = await j.join(uri, realm)
    session = AsyncSession(details)

    session._on_disconnect(disconnect_callback)

    if connect_callback is not None:
        await connect_callback()

    return session


async def connect_anonymous(uri: str, realm: str) -> AsyncSession:
    return await connect(uri, realm)


async def connect_ticket(uri: str, realm: str, authid: str, ticket: str) -> AsyncSession:
    ticket_authenticator = auth.TicketAuthenticator(authid, ticket)

    return await connect(uri, realm, ticket_authenticator)


async def connect_wampcra(uri: str, realm: str, authid: str, secret: str) -> AsyncSession:
    wampcra_authenticator = auth.WAMPCRAAuthenticator(authid, secret)

    return await connect(uri, realm, wampcra_authenticator)


async def connect_cryptosign(uri: str, realm: str, authid: str, private_key: str) -> AsyncSession:
    cryptosign_authenticator = auth.CryptoSignAuthenticator(authid, private_key)

    return await connect(uri, realm, cryptosign_authenticator)
