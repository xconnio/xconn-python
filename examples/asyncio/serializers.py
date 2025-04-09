from xconn.async_session import AsyncSession
from xconn import AsyncClient, JSONSerializer, CBORSerializer, MsgPackSerializer


async def connect_json(url: str, realm: str) -> AsyncSession:
    client = AsyncClient(serializer=JSONSerializer())

    return await client.connect(url, realm)


async def connect_cbor(url: str, realm: str) -> AsyncSession:
    client = AsyncClient(serializer=CBORSerializer())

    return await client.connect(url, realm)


async def connect_msgpack(url: str, realm: str) -> AsyncSession:
    client = AsyncClient(serializer=MsgPackSerializer())

    return await client.connect(url, realm)
