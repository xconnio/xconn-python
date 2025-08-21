from typing import Callable
from urllib.parse import urlparse

from wampproto import auth, serializers

from xconn import types
from xconn.session import Session
from xconn.joiner import WebsocketsJoiner, RawSocketJoiner


class Client:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator = auth.AnonymousAuthenticator(""),
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
        return connect(
            uri, realm, self._authenticator, self._serializer, self._ws_config, connect_callback, disconnect_callback
        )


def connect(
    uri: str,
    realm: str,
    authenticator: auth.IClientAuthenticator = None,
    serializer: serializers.Serializer = serializers.CBORSerializer(),
    ws_config: types.WebsocketConfig = types.WebsocketConfig(),
    connect_callback: Callable[[], None] | None = None,
    disconnect_callback: Callable[[], None] | None = None,
) -> Session:
    parsed = urlparse(uri)
    if parsed.scheme == "ws" or parsed.scheme == "wss" or parsed.scheme == "unix+ws":
        j = WebsocketsJoiner(authenticator, serializer, ws_config)
    elif (
        parsed.scheme == "rs"
        or parsed.scheme == "rss"
        or parsed.scheme == "tcp"
        or parsed.scheme == "tcps"
        or parsed.scheme == "unix"
        or parsed.scheme == "unix+rs"
    ):
        j = RawSocketJoiner(authenticator, serializer)
    else:
        raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

    details = j.join(uri, realm)
    session = Session(details)

    session._on_disconnect(disconnect_callback)

    if connect_callback is not None:
        connect_callback()

    return session


def connect_anonymous(uri: str, realm: str) -> Session:
    return connect(uri, realm)


def connect_ticket(uri: str, realm: str, authid: str, ticket: str) -> Session:
    ticket_authenticator = auth.TicketAuthenticator(authid, ticket)

    return connect(uri, realm, ticket_authenticator)


def connect_wampcra(uri: str, realm: str, authid: str, secret: str) -> Session:
    wampcra_authenticator = auth.WAMPCRAAuthenticator(authid, secret)

    return connect(uri, realm, wampcra_authenticator)


def connect_cryptosign(uri: str, realm: str, authid: str, private_key: str) -> Session:
    cryptosign_authenticator = auth.CryptoSignAuthenticator(authid, private_key)

    return connect(uri, realm, cryptosign_authenticator)
