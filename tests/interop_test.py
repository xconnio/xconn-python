import pytest
from wampproto import auth, serializers

from xconn.client import Client

XCONN_URL = "ws://localhost:8080/ws"
CROSSBAR_URL = "ws://localhost:8081/ws"
REALM = "realm1"
PROCEDURE_ADD = "io.xconn.backend.add2"


@pytest.mark.parametrize("url", [XCONN_URL, CROSSBAR_URL])
@pytest.mark.parametrize(
    "serializer", [serializers.JSONSerializer(), serializers.CBORSerializer(), serializers.MsgPackSerializer()]
)
@pytest.mark.parametrize(
    "authenticator",
    [
        auth.AnonymousAuthenticator(""),
        auth.TicketAuthenticator("ticket-user", "ticket-pass", {}),
        auth.WAMPCRAAuthenticator("wamp-cra-user", "cra-secret", {}),
        # FIXME: WAMPCRA with salt is broken in crossbar
        # auth.WAMPCRAAuthenticator("wamp-cra-salt-user", "cra-salt-secret", {}),
        auth.CryptoSignAuthenticator(
            "cryptosign-user",
            "150085398329d255ad69e82bf47ced397bcec5b8fbeecd28a80edbbd85b49081",
            {},
        ),
    ],
)
def test_auth_methods(url: str, serializer: serializers.Serializer, authenticator: auth.IClientAuthenticator):
    client = Client(authenticator=authenticator, serializer=serializer)
    session = client.connect(url, REALM)
    result = session.call(PROCEDURE_ADD, 2, 2)
    assert result.args[0] == 4

    session.leave()
