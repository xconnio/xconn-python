import os
import asyncio
import hashlib

import pytest
from wampproto import serializers

from xconn import AsyncClient
from xconn.types import Event
from xconn.async_client import connect_anonymous


async def test_pubsub():
    client1 = await connect_anonymous("ws://localhost:8079/ws", "realm1")
    client2 = await connect_anonymous("ws://localhost:8079/ws", "realm1")

    args = ["client1", "client2"]

    async def event_handler_with_args(event: Event):
        assert event.args == args
        assert event.kwargs is None

    args_subscription = await client1.subscribe("io.xconn.pubsub.args", event_handler_with_args)
    await client2.publish("io.xconn.pubsub.args", args, options={"acknowledge": True})
    await args_subscription.unsubscribe()

    kwargs = {"foo": "bar", "baz": {"k": "v"}}

    async def event_handler_with_kwargs(event: Event):
        assert event.args == []
        assert event.kwargs == kwargs

    subscription = await client1.subscribe("io.xconn.pubsub.kwargs", event_handler_with_kwargs)
    await client2.publish("io.xconn.pubsub.kwargs", kwargs=kwargs, options={"acknowledge": True})

    await subscription.unsubscribe()

    await client2.leave()
    await client1.leave()


@pytest.mark.parametrize("serializer", [serializers.CBORSerializer(), serializers.MsgPackSerializer()])
async def test_pubsub_with_various_data(serializer: serializers.Serializer):
    async_client = AsyncClient(serializer=serializer)
    client1 = await async_client.connect("ws://localhost:8079/ws", "realm1")
    async_client2 = AsyncClient(serializer=serializer)
    client2 = await async_client2.connect("ws://localhost:8079/ws", "realm1")

    async def event_handler(inv: Event):
        payload: bytes = inv.kwargs["payload"]
        checksum: bytes = inv.kwargs["checksum"]

        calculated_checksum = hashlib.sha256(payload).digest()
        assert calculated_checksum == checksum, f"Checksum mismatch! got {calculated_checksum}, expected {checksum}"

    await client1.subscribe("io.xconn.pubsub.event_handler", event_handler)

    async def send_payload(size_bytes: int):
        payload = os.urandom(size_bytes)
        checksum = hashlib.sha256(payload).digest()

        await client2.publish("io.xconn.pubsub.event_handler", kwargs={"payload": payload, "checksum": checksum})

    # test call with different payload sizes
    sizes = [1024 * n for n in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1023]]

    await asyncio.gather(*(send_payload(size) for size in sizes))

    await client1.leave()
    await client2.leave()
