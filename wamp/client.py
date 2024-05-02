from wampproto import auth, serializers

from wamp.joiner import WebsocketsJoiner
from wamp.session import Session


class Client:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    def connect(self, url: str, realm: str) -> Session:
        j = WebsocketsJoiner(self._authenticator, self._serializer)
        details = j.join(url, realm)

        return Session(details)
