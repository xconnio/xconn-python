import base64
from pathlib import Path
from typing import Type, TypeVar, Any

import capnp
from google.protobuf.message import Message

from xconn.client import connect_anonymous
from xconn import codec
from xconn.types import Invocation, Result, Event
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


def test_pubsub_object():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(Base64Codec())

    def event_handler(event: Event):
        assert event.args[0] == "hello"

    session.subscribe_object("io.xconn.object", event_handler, String)

    session.publish_object("io.xconn.object", String("hello"))

    session.leave()


def test_register_object_one_param_with_return_type():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    def create_profile_handler(prof: ProfileCreate) -> ProfileGet:
        return ProfileGet(
            id="356",
            username=prof.username,
            email=prof.email,
            age=prof.age,
            created_at="2025-10-30T17:00:00Z",
        )

    session.register_object("io.xconn.profile.create", create_profile_handler)

    profile_create = ProfileCreate(username="john", email="john@xconn.io", age=25)
    result = session.call("io.xconn.profile.create", [profile_create.SerializeToString()])

    profile = ProfileGet()
    profile.ParseFromString(result.args[0])

    assert profile.id == "356"
    assert profile.username == "john"
    assert profile.email == "john@xconn.io"
    assert profile.age == 25
    assert profile.created_at == "2025-10-30T17:00:00Z"

    session.leave()


def test_register_object_no_param():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    options = {"flag": False}

    def invocation_handler() -> None:
        options["flag"] = True

    session.register_object("io.xconn.param.none", invocation_handler)

    result = session.call("io.xconn.param.none")

    assert options["flag"] is True
    assert result.args is None
    assert result.kwargs is None

    session.leave()


def test_register_object_no_param_with_return():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    def get_profile_handler() -> ProfileGet:
        return ProfileGet(
            id="636",
            username="admin",
            email="admin@xconn.io",
            age=30,
            created_at="2025-10-30T17:00:00Z",
        )

    session.register_object("io.xconn.profile.get", get_profile_handler)

    result = session.call("io.xconn.profile.get")

    profile = ProfileGet()
    profile.ParseFromString(result.args[0])

    assert profile.id == "636"
    assert profile.username == "admin"
    assert profile.email == "admin@xconn.io"
    assert profile.age == 30
    assert profile.created_at == "2025-10-30T17:00:00Z"

    session.leave()


T = TypeVar("T")
SCHEMA_PATH = Path(__file__).parent / "user.capnp"
user_capnp = capnp.load(str(SCHEMA_PATH))

UserCreate = user_capnp.UserCreate
UserGet = user_capnp.UserGet


class CapnpProtoCodec(codec.Codec[T]):
    def name(self) -> str:
        return "capnproto"

    def encode(self, obj: Any) -> bytes:
        return obj.to_bytes_packed()

    def decode(self, data: bytes, out_type: Type[T]) -> T:
        return out_type.from_bytes_packed(data)


def test_register_object_capnproto():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(CapnpProtoCodec())

    def create_handler(user_create: UserCreate) -> UserGet:
        user_get = UserGet.new_message()
        user_get.id = 999
        user_get.name = user_create.name
        user_get.email = user_create.email
        user_get.age = user_create.age
        user_get.isAdmin = False

        return user_get

    session.register_object("io.xconn.user.create", create_handler)

    new_user = UserCreate.new_message()
    new_user.name = "john"
    new_user.email = "john@xconn.io"
    new_user.age = 35

    result = session.call("io.xconn.user.create", [new_user.to_bytes_packed()])
    user = UserGet.from_bytes_packed(result.args[0])

    assert user.id == 999
    assert user.name == "john"
    assert user.email == "john@xconn.io"
    assert user.age == 35
    assert not user.isAdmin

    session.leave()


def test_call_object_capnproto():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(CapnpProtoCodec())

    def invocation_handler(inv: Invocation) -> Result:
        user_create = UserCreate.from_bytes_packed(inv.args[0])

        user_get = UserGet.new_message()
        user_get.id = 78
        user_get.name = user_create.name
        user_get.email = user_create.email
        user_get.age = user_create.age
        user_get.isAdmin = True

        return Result(args=[user_get.to_bytes_packed()])

    session.register("io.xconn.user.create", invocation_handler)
    new_user = UserCreate.new_message()
    new_user.name = "alice"
    new_user.email = "alice@xconn.io"
    new_user.age = 23

    result: UserGet = session.call_object("io.xconn.user.create", new_user, UserGet)
    assert result.id == 78
    assert result.name == "alice"
    assert result.email == "alice@xconn.io"
    assert result.age == 23
    assert result.isAdmin

    session.leave()


def test_pubsub_capnproto():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(CapnpProtoCodec())

    def event_handler(event: Event):
        user: UserGet = event.args[0]
        assert user.name == "alice"
        assert user.email == "alice@xconn.io"
        assert user.age == 21

    session.subscribe_object("io.xconn.object", event_handler, UserCreate)

    new_user = UserCreate.new_message()
    new_user.name = "alice"
    new_user.email = "alice@xconn.io"
    new_user.age = 21

    session.publish_object("io.xconn.object", new_user)

    session.leave()
