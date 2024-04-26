from collections import deque

from wampproto import messages, serializers

from wamp import router, types


class MockBaseSession(types.IBaseSession):
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

    def send(self, data: bytes):
        self.messages.append(data)

    def receive(self) -> bytes:
        return self.messages.popleft()

    def send_message(self, msg: messages.Message):
        self.send(self._serializer.serialize(msg))

    def receive_message(self) -> messages.Message:
        return self._serializer.deserialize(self.receive())

    def register(self, procedure: str, r: router.Router):
        reg = messages.Register(2, procedure)
        r.receive_message(self, reg)

        registered = self.receive_message()
        assert isinstance(registered, messages.Registered)

    def call(self, procedure: str, r: router.Router):
        call = messages.Call(3, procedure)
        r.receive_message(self, call)

        invocation = self._other.receive_message()
        assert isinstance(invocation, messages.Invocation)

        yield_ = messages.Yield(3)
        r.receive_message(self._other, yield_)

        result = self.receive_message()
        assert isinstance(result, messages.Result)

        return result


def test_router():
    caller = MockBaseSession(1, "realm1", "john", "anonymous", serializers.JSONSerializer())
    callee = MockBaseSession(2, "realm1", "alex", "anonymous", serializers.JSONSerializer())

    caller.set_other(callee)
    callee.set_other(caller)

    r = router.Router()
    r.add_realm("realm1")
    r.attach_client(callee)
    r.attach_client(caller)

    r.receive_message(caller, messages.Call(1, "foo.bar"))

    err = caller.receive_message()
    assert isinstance(err, messages.Error)
    assert err.uri == "wamp.error.no_such_procedure"

    callee.register("foo.bar", r)
    caller.call("foo.bar", r)
