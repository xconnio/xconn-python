from xconn.app import App, Component, register, subscribe
from xconn.client import Client
from xconn.async_client import AsyncClient
from xconn.router import Router
from xconn.server import Server
from xconn.utils import run
from xconn._client.helpers import connect

from wampproto.auth import (
    AnonymousAuthenticator,
    TicketAuthenticator,
    WAMPCRAAuthenticator,
    CryptoSignAuthenticator,
)

from wampproto.serializers import (
    JSONSerializer,
    MsgPackSerializer,
    CBORSerializer,
)

__all__ = [
    "App",
    "Component",
    "register",
    "subscribe",
    "Client",
    "AsyncClient",
    "Router",
    "Server",
    # export authenticators
    "AnonymousAuthenticator",
    "TicketAuthenticator",
    "WAMPCRAAuthenticator",
    "CryptoSignAuthenticator",
    # export serializers
    "JSONSerializer",
    "MsgPackSerializer",
    "CBORSerializer",
    # runner for async client
    "run",
    # xcorn connect function
    "connect",
]

_capnp_import_error = None
try:
    from xconn.helpers import CapnProtoSerializer

    __all__.extend(["CapnProtoSerializer"])
except ImportError as e:
    _capnp_import_error = e

    class CapnProtoSerializer:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "Cap'n Proto serializer support is not installed.\nInstall it with:\n  uv pip install xconn[capnproto]"
            ) from _capnp_import_error
