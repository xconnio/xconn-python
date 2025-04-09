from wampproto.serializers import Serializer
from wampproto.auth import IClientAuthenticator

from xconn.session import Session
from xconn import Client, TicketAuthenticator, WAMPCRAAuthenticator, CryptoSignAuthenticator


def connect(url: str, realm: str, authenticator: IClientAuthenticator, serializer: Serializer) -> Session:
    client = Client(authenticator, serializer)

    return client.connect(url, realm)


def connect_ticket(url: str, realm: str, authid: str, ticket: str, serializer: Serializer) -> Session:
    client = Client(TicketAuthenticator(authid, ticket), serializer)

    return client.connect(url, realm)


def connect_cra(url: str, realm: str, authid: str, secret: str, serializer: Serializer) -> Session:
    client = Client(WAMPCRAAuthenticator(authid, secret), serializer)

    return client.connect(url, realm)


def connect_cryptosign(url: str, realm: str, authid: str, private_key: str, serializer: Serializer) -> Session:
    client = Client(CryptoSignAuthenticator(authid, private_key), serializer)

    return client.connect(url, realm)
