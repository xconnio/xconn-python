from wampproto.serializers import Serializer
from wampproto.auth import IClientAuthenticator

from xconn.async_session import AsyncSession
from xconn import AsyncClient, TicketAuthenticator, WAMPCRAAuthenticator, CryptoSignAuthenticator


async def connect(url: str, realm: str, authenticator: IClientAuthenticator, serializer: Serializer) -> AsyncSession:
    client = AsyncClient(authenticator, serializer)

    return await client.connect(url, realm)


async def connect_ticket(url: str, realm: str, authid: str, ticket: str, serializer: Serializer) -> AsyncSession:
    client = AsyncClient(TicketAuthenticator(authid, ticket), serializer)

    return await client.connect(url, realm)


async def connect_cra(url: str, realm: str, authid: str, secret: str, serializer: Serializer) -> AsyncSession:
    client = AsyncClient(WAMPCRAAuthenticator(authid, secret), serializer)

    return await client.connect(url, realm)


async def connect_cryptosign(
    url: str, realm: str, authid: str, private_key: str, serializer: Serializer
) -> AsyncSession:
    client = AsyncClient(CryptoSignAuthenticator(authid, private_key), serializer)

    return await client.connect(url, realm)
