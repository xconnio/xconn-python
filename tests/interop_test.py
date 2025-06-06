import pytest
from wampproto import auth, serializers

from xconn.client import Client, AsyncClient
from xconn.types import Result, Event, Invocation

XCONN_URL = "ws://localhost:8080/ws"
CROSSBAR_URL = "ws://localhost:8081/ws"
REALM = "realm1"
PROCEDURE_ADD = "io.xconn.backend.add2"

ROUTER_URL = [XCONN_URL, CROSSBAR_URL]
SERIALIZERS = [serializers.JSONSerializer(), serializers.CBORSerializer(), serializers.MsgPackSerializer()]
AUTHENTICATORS = [
    auth.AnonymousAuthenticator(""),
    auth.TicketAuthenticator("ticket-user", "ticket-pass", {}),
    auth.WAMPCRAAuthenticator("wamp-cra-user", "cra-secret", {}),
    auth.WAMPCRAAuthenticator("wamp-cra-salt-user", "cra-salt-secret", {}),
    auth.CryptoSignAuthenticator(
        "cryptosign-user",
        "150085398329d255ad69e82bf47ced397bcec5b8fbeecd28a80edbbd85b49081",
        {},
    ),
]


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
def test_call(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    client = Client(authenticator=authenticator, serializer=serializer)
    session = client.connect(url, REALM)
    result = session.call(PROCEDURE_ADD, 2, 2)
    assert result.args[0] == 4

    session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
def test_pubsub(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    args = ["hello", "wamp"]

    def event_handler(event: Event):
        assert event.args == args

    client = Client(authenticator=authenticator, serializer=serializer)
    session = client.connect(url, REALM)
    sub = session.subscribe("io.xconn.test", event_handler, options={"acknowledge": True})
    session.publish("io.xconn.test", args)

    session.unsubscribe(sub)

    session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
def test_rpc(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    args = ["hello", "wamp"]

    def inv_handler(inv: Invocation):
        return Result(args=inv.args)

    client = Client(authenticator=authenticator, serializer=serializer)
    session = client.connect(url, REALM)
    reg = session.register("io.xconn.test", inv_handler)
    result = session.call("io.xconn.test", *args)
    assert result.args == args

    session.unregister(reg)

    session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
async def test_pubsub_async(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    args = ["hello", "wamp"]

    async def event_handler(event: Event):
        assert event.args == args

    client = AsyncClient(authenticator=authenticator, serializer=serializer)
    session = await client.connect(url, REALM)
    sub = await session.subscribe("io.xconn.test", event_handler, options={"acknowledge": True})
    await session.publish("io.xconn.test", args)

    await session.unsubscribe(sub)

    await session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
async def test_pubsub_async_with_sync_event_handler(
    url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator
):
    args = ["hello", "wamp"]

    def event_handler(event: Event):
        assert event.args == args

    client = AsyncClient(authenticator=authenticator, serializer=serializer)
    session = await client.connect(url, REALM)
    topic = "io.xconn.test"
    with pytest.raises(
        RuntimeError, match=f"function {event_handler.__name__} for topic '{topic}' must be a coroutine"
    ):
        await session.subscribe(topic, event_handler, options={"acknowledge": True})

    await session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
async def test_rpc_async(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    args = ["hello", "wamp"]

    async def inv_handler(inv: Invocation):
        return Result(args=inv.args)

    client = AsyncClient(authenticator=authenticator, serializer=serializer)
    session = await client.connect(url, REALM)
    reg = await session.register("io.xconn.test", inv_handler)
    result = await session.call("io.xconn.test", *args)
    assert result.args == args

    await session.unregister(reg)

    await session.leave()


@pytest.mark.parametrize("url", ROUTER_URL)
@pytest.mark.parametrize("serializer", SERIALIZERS)
@pytest.mark.parametrize("authenticator", AUTHENTICATORS)
async def test_rpc_async_with_sync_invocation_handler(
    url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator
):
    def inv_handler(inv: Invocation):
        return Result(args=inv.args)

    client = AsyncClient(authenticator=authenticator, serializer=serializer)
    session = await client.connect(url, REALM)
    procedure = "io.xconn.test"
    with pytest.raises(
        RuntimeError, match=f"function {inv_handler.__name__} for procedure '{procedure}' must be a coroutine"
    ):
        await session.register(procedure, inv_handler)

    await session.leave()
