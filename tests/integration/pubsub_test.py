import concurrent
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from wampproto import serializers

from xconn import Client
from xconn.types import Event
from xconn.client import connect_anonymous


def test_pubsub():
    client1 = connect_anonymous("ws://localhost:8079/ws", "realm1")
    client2 = connect_anonymous("ws://localhost:8079/ws", "realm1")

    args = ["client1", "client2"]

    def event_handler_with_args(event: Event):
        assert event.args == args
        assert event.kwargs is None

    args_subscription = client1.subscribe("io.xconn.pubsub.args", event_handler_with_args)
    client2.publish("io.xconn.pubsub.args", args, options={"acknowledge": True})
    args_subscription.unsubscribe()

    kwargs = {"foo": "bar", "baz": {"k": "v"}}

    def event_handler_with_kwargs(event: Event):
        assert event.args == []
        assert event.kwargs == kwargs

    registration = client1.subscribe("io.xconn.pubsub.kwargs", event_handler_with_kwargs)
    client2.publish("io.xconn.pubsub.kwargs", kwargs=kwargs, options={"acknowledge": True})

    registration.unsubscribe()

    client2.leave()
    client1.leave()


@pytest.mark.parametrize("serializer", [serializers.CBORSerializer(), serializers.MsgPackSerializer()])
def test_pubsub_with_various_data(serializer: serializers.Serializer):
    client1 = Client(serializer=serializer).connect("ws://localhost:8079/ws", "realm1")
    client2 = Client(serializer=serializer).connect("ws://localhost:8079/ws", "realm1")

    def event_handler(inv: Event):
        payload: bytes = inv.kwargs["payload"]
        checksum: bytes = inv.kwargs["checksum"]

        calculated_checksum = hashlib.sha256(payload).digest()
        assert calculated_checksum == checksum, f"Checksum mismatch! got {calculated_checksum}, expected {checksum}"

    client1.subscribe("io.xconn.pubsub.event_handler", event_handler)

    def send_payload(size_bytes: int):
        payload = os.urandom(size_bytes)
        checksum = hashlib.sha256(payload).digest()

        client2.publish("io.xconn.pubsub.event_handler", kwargs={"payload": payload, "checksum": checksum})

    # test call with different payload sizes
    sizes = [1024 * n for n in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1023]]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(send_payload, size) for size in sizes]

        for future in concurrent.futures.as_completed(futures):
            future.result()

    client1.leave()
    client2.leave()
