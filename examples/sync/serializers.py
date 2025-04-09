from xconn.session import Session
from xconn import Client, JSONSerializer, CBORSerializer, MsgPackSerializer


def connect_json(url: str, realm: str) -> Session:
    client = Client(serializer=JSONSerializer())

    return client.connect(url, realm)


def connect_cbor(url: str, realm: str) -> Session:
    client = Client(serializer=CBORSerializer())

    return client.connect(url, realm)


def connect_msgpack(url: str, realm: str) -> Session:
    client = Client(serializer=MsgPackSerializer())

    return client.connect(url, realm)
