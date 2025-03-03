from wampproto import auth, serializers

from xconn.session import Session, AsyncSession
from xconn.joiner import WebsocketsJoiner, AsyncWebsocketsJoiner


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


class AsyncClient:
    def __init__(
        self,
        authenticator: auth.IClientAuthenticator,
        serializer: serializers.Serializer = serializers.JSONSerializer(),
    ):
        self._authenticator = authenticator
        self._serializer = serializer

    async def connect(self, url: str, realm: str) -> AsyncSession:
        j = AsyncWebsocketsJoiner(self._authenticator, self._serializer)
        details = await j.join(url, realm)

        return AsyncSession(details)
