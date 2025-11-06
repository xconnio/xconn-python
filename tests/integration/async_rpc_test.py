import os
import asyncio
import hashlib

import pytest
from wampproto import serializers

from xconn import AsyncClient
from xconn.types import Invocation
from xconn.async_client import connect_anonymous
from xconn.exception import ApplicationError


async def test_rpc():
    client1 = await connect_anonymous("ws://localhost:8079/ws", "realm1")
    client2 = await connect_anonymous("ws://localhost:8079/ws", "realm1")

    args = ["client1", "client2"]

    async def inv_handler_with_args(inv: Invocation):
        assert inv.args == args
        assert inv.kwargs is None

    args_registration = await client1.register("io.xconn.rpc.args", inv_handler_with_args)
    await client2.call("io.xconn.rpc.args", args)
    await args_registration.unregister()

    with pytest.raises(ApplicationError, match="wamp.error.no_such_procedure"):
        await client2.call("io.xconn.rpc.args", args)

    kwargs = {"foo": "bar", "baz": {"k": "v"}}

    async def inv_handler_with_kwargs(inv: Invocation):
        assert inv.args == []
        assert inv.kwargs == kwargs

    registration = await client1.register("io.xconn.rpc.kwargs", inv_handler_with_kwargs)
    await client2.call("io.xconn.rpc.kwargs", kwargs=kwargs)

    await registration.unregister()

    await client2.leave()
    await client1.leave()


@pytest.mark.parametrize(
    "serializer", [serializers.CBORSerializer(), serializers.MsgPackSerializer()]
)
async def test_rpc_with_various_data(serializer: serializers.Serializer):
    async_client = AsyncClient(serializer=serializer)
    client1 = await async_client.connect("ws://localhost:8079/ws", "realm1")
    async_client2 = AsyncClient(serializer=serializer)
    client2 = await async_client2.connect("ws://localhost:8079/ws", "realm1")

    async def inv_handler(inv: Invocation):
        payload: bytes = inv.kwargs["payload"]
        checksum: bytes = inv.kwargs["checksum"]

        calculated_checksum = hashlib.sha256(payload).digest()
        assert calculated_checksum == checksum, f"Checksum mismatch! got {calculated_checksum}, expected {checksum}"

    await client1.register("io.xconn.rpc.inv_handler", inv_handler)

    async def send_payload(size_bytes: int):
        payload = os.urandom(size_bytes)
        checksum = hashlib.sha256(payload).digest()

        await client2.call("io.xconn.rpc.inv_handler", kwargs={"payload": payload, "checksum": checksum})

    # test call with different payload sizes
    sizes = [1024 * n for n in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1023]]

    await asyncio.gather(*(send_payload(size) for size in sizes))

    await client1.leave()
    await client2.leave()
