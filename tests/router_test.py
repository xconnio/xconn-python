from collections import deque

import pytest
from wampproto import messages, serializers

from xconn import router, types


class MockBaseSession(types.IAsyncBaseSession):
    def __init__(self, sid: int, realm: str, authid: str, authrole: str, serializer: serializers.Serializer):
        super().__init__()
        self._id = sid
        self._realm = realm
        self._authid = authid
        self._authrole = authrole
        self._serializer = serializer

        self._other: MockBaseSession = None
        self.messages = deque()

    def set_other(self, other: "MockBaseSession"):
        self._other = other

    @property
    def id(self) -> int:
        return self._id

    @property
    def realm(self) -> str:
        return self._realm

    @property
    def authid(self) -> str:
        return self._authid

    @property
    def authrole(self) -> str:
        return self._authrole

    async def send(self, data: bytes):
        self.messages.append(data)

    async def receive(self) -> bytes:
        return self.messages.popleft()

    async def send_message(self, msg: messages.Message):
        await self.send(self._serializer.serialize(msg))

    async def receive_message(self) -> messages.Message:
        return self._serializer.deserialize(await self.receive())

    async def register(self, procedure: str, r: router.Router):
        reg = messages.Register(2, procedure)
        await r.receive_message(self, reg)

        registered = await self.receive_message()
        assert isinstance(registered, messages.Registered)

    async def call(self, procedure: str, r: router.Router):
        call = messages.Call(3, procedure)
        await r.receive_message(self, call)

        invocation = await self._other.receive_message()
        assert isinstance(invocation, messages.Invocation)

        yield_ = messages.Yield(3)
        await r.receive_message(self._other, yield_)

        result = await self.receive_message()
        assert isinstance(result, messages.Result)

        return result


@pytest.mark.asyncio
async def test_router():
    caller = MockBaseSession(1, "realm1", "john", "anonymous", serializers.JSONSerializer())
    callee = MockBaseSession(2, "realm1", "alex", "anonymous", serializers.JSONSerializer())

    caller.set_other(callee)
    callee.set_other(caller)

    r = router.Router()
    r.add_realm("realm1")
    r.attach_client(callee)
    r.attach_client(caller)

    await r.receive_message(caller, messages.Call(1, "foo.bar"))

    err = await caller.receive_message()
    assert isinstance(err, messages.Error)
    assert err.uri == "wamp.error.no_such_procedure"

    await callee.register("foo.bar", r)
    await caller.call("foo.bar", r)
