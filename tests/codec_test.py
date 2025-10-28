import base64
from typing import Type

from google.protobuf.message import Message

from xconn.client import connect_anonymous
from xconn import codec
from xconn.types import Invocation, Result
from tests.profile_pb2 import ProfileCreate, ProfileGet


class String(str):
    pass


class Base64Codec(codec.Codec[String]):
    def name(self) -> str:
        return "base64"

    def encode(self, obj: String) -> str:
        return base64.b64encode(obj.encode("utf-8")).decode("utf-8")

    def decode(self, data: str, out_type: Type[String]) -> String:
        return out_type(base64.b64decode(data.encode("utf-8")).decode())


def test_base64_codec():
    encoder = Base64Codec()
    encoded = encoder.encode(String("hello"))
    assert isinstance(encoded, str)

    decoded = encoder.decode(encoded, String)
    assert isinstance(decoded, String)
    assert decoded == "hello"


def test_something():
    # session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    # session.set_payload_codec(Base64Codec())
    # result = session.call_object("io.xconn.object", String("hello"), String)
    # print(result)
    # session.leave()
    pass


class ProtobufCodec(codec.Codec[Message]):
    def name(self) -> str:
        return "protobuf"

    def encode(self, obj: Message) -> bytes:
        return obj.SerializeToString()

    def decode(self, data: bytes, out_type: Type[Message]) -> Message:
        msg = out_type()
        msg.ParseFromString(data)
        return msg


def test_protobuf_codec():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    def inv_handler(inv: Invocation) -> Result:
        profile = ProfileCreate()
        profile.ParseFromString(inv.args[0])

        profile_get = ProfileGet(
            id="123",
            username=profile.username,
            email=profile.email,
            age=profile.age,
            created_at="2025-10-28T17:00:00Z",
        )

        return Result(args=[profile_get.SerializeToString()])

    session.register("io.xconn.profile.create", inv_handler)
    create_msg = ProfileCreate(username="john", email="john@xconn.io", age=25)

    result = session.call_object("io.xconn.profile.create", create_msg, ProfileGet)
    assert isinstance(result, ProfileGet)
    assert result.username == "john"
    assert result.email == "john@xconn.io"
    assert result.age == 25
    assert result.id == "123"
    assert result.created_at == "2025-10-28T17:00:00Z"

    session.leave()
