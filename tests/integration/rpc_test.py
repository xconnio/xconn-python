import concurrent
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from wampproto import serializers

from xconn import Client
from xconn.types import Invocation
from xconn.client import connect_anonymous
from xconn.exception import ApplicationError


def test_rpc():
    client1 = connect_anonymous("ws://localhost:8079/ws", "realm1")
    client2 = connect_anonymous("ws://localhost:8079/ws", "realm1")

    args = ["client1", "client2"]

    def inv_handler_with_args(inv: Invocation):
        assert inv.args == args
        assert inv.kwargs is None

    args_registration = client1.register("io.xconn.rpc.args", inv_handler_with_args)
    client2.call("io.xconn.rpc.args", args)
    args_registration.unregister()

    with pytest.raises(ApplicationError, match="wamp.error.no_such_procedure"):
        client2.call("io.xconn.rpc.args", args)

    kwargs = {"foo": "bar", "baz": {"k": "v"}}

    def inv_handler_with_kwargs(inv: Invocation):
        assert inv.args == []
        assert inv.kwargs == kwargs

    registration = client1.register("io.xconn.rpc.kwargs", inv_handler_with_kwargs)
    client2.call("io.xconn.rpc.kwargs", kwargs=kwargs)

    registration.unregister()

    client2.leave()
    client1.leave()


@pytest.mark.parametrize(
    "serializer", [serializers.CBORSerializer(), serializers.MsgPackSerializer()]
)
def test_rpc_with_various_data(serializer: serializers.Serializer):
    client1 = Client(serializer=serializer).connect("ws://localhost:8079/ws", "realm1")
    client2 = Client(serializer=serializer).connect("ws://localhost:8079/ws", "realm1")

    def inv_handler(inv: Invocation):
        payload: bytes = inv.kwargs["payload"]
        checksum: bytes = inv.kwargs["checksum"]

        calculated_checksum = hashlib.sha256(payload).digest()
        assert calculated_checksum == checksum, f"Checksum mismatch! got {calculated_checksum}, expected {checksum}"

    client1.register("io.xconn.rpc.inv_handler", inv_handler)

    def send_payload(size_bytes: int):
        payload = os.urandom(size_bytes)
        checksum = hashlib.sha256(payload).digest()

        client2.call("io.xconn.rpc.inv_handler", kwargs={"payload": payload, "checksum": checksum})

    # test call with different payload sizes
    sizes = [1024 * n for n in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1023]]

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(send_payload, size) for size in sizes]

        for future in concurrent.futures.as_completed(futures):
            future.result()

    client1.leave()
    client2.leave()
