import os
from pathlib import Path
from typing import Type, TypeVar

import capnp
from google.protobuf.message import Message

from xconn.client import connect_anonymous
from xconn.codec import Codec
from xconn.types import Event, OutgoingDataMessage, IncomingDataMessage
from tests.schemas.profile_pb2 import ProfileCreate, ProfileGet


T = TypeVar("T", bound=Message)


class ProtobufCodec(Codec[T]):
    def name(self) -> str:
        return "protobuf"

    def encode(self, obj: T) -> OutgoingDataMessage:
        payload = obj.SerializeToString()
        return OutgoingDataMessage(args=[payload], kwargs={}, details={})

    def decode(self, msg: IncomingDataMessage, out_type: Type[T]) -> T:
        if len(msg.args) == 0 or not isinstance(msg.args[0], bytes):
            raise ValueError("ProtobufCodec: cannot decode, expected first arg to be bytes")

        obj = out_type()
        obj.ParseFromString(msg.args[0])
        return obj


def test_rpc_object_protobuf():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    def inv_handler(profile: ProfileCreate) -> ProfileGet:
        return ProfileGet(
            id="123",
            username=profile.username,
            email=profile.email,
            age=profile.age,
            created_at="2025-10-28T17:00:00Z",
        )

    session.register_object("io.xconn.profile.create", inv_handler)
    create_msg = ProfileCreate(username="john", email="john@xconn.io", age=25)

    result = session.call_object("io.xconn.profile.create", create_msg, ProfileGet)
    assert isinstance(result, ProfileGet)
    assert result.username == "john"
    assert result.email == "john@xconn.io"
    assert result.age == 25
    assert result.id == "123"
    assert result.created_at == "2025-10-28T17:00:00Z"

    session.leave()


def test_pubsub_protobuf():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    def event_handler(event: Event):
        user: ProfileCreate = event.args[0]
        assert user.username == "john"
        assert user.email == "john@xconn.io"
        assert user.age == 25

    session.subscribe_object("io.xconn.object", event_handler, ProfileCreate)

    create_msg = ProfileCreate(username="john", email="john@xconn.io", age=25)
    session.publish_object("io.xconn.object", create_msg)

    session.leave()


def test_rpc_object_one_param_with_return_type():
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
    profile = session.call_object("io.xconn.profile.create", profile_create, ProfileGet)

    assert profile.id == "356"
    assert profile.username == "john"
    assert profile.email == "john@xconn.io"
    assert profile.age == 25
    assert profile.created_at == "2025-10-30T17:00:00Z"

    session.leave()


def test_rpc_object_no_param():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(ProtobufCodec())

    options = {"flag": False}

    def invocation_handler() -> None:
        options["flag"] = True

    session.register_object("io.xconn.param.none", invocation_handler)

    result = session.call_object("io.xconn.param.none")

    assert options["flag"] is True
    assert result is None

    session.leave()


def test_rpc_object_no_param_with_return():
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

    profile = session.call_object("io.xconn.profile.get", return_type=ProfileGet)

    assert profile.id == "636"
    assert profile.username == "admin"
    assert profile.email == "admin@xconn.io"
    assert profile.age == 30
    assert profile.created_at == "2025-10-30T17:00:00Z"

    session.leave()


T = TypeVar("T")

root_dir = Path(__file__).resolve().parent
module_file = os.path.join(root_dir, "schemas", "user.capnp")
user_capnp = capnp.load(str(module_file))

UserCreate = user_capnp.UserCreate
UserGet = user_capnp.UserGet


class CapnpProtoCodec(Codec[T]):
    def name(self) -> str:
        return "capnproto"

    def encode(self, obj: T) -> OutgoingDataMessage:
        payload = obj.to_bytes_packed()
        return OutgoingDataMessage(args=[payload], kwargs={}, details={})

    def decode(self, msg: IncomingDataMessage, out_type: Type[T]) -> T:
        if len(msg.args) == 0 or not isinstance(msg.args[0], bytes):
            raise ValueError("CapnpProtoCodec: cannot decode, expected first arg to be bytes")

        return out_type.from_bytes_packed(msg.args[0])


def test_rpc_object_capnproto():
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

    user = session.call_object("io.xconn.user.create", new_user, UserGet)

    assert user.id == 999
    assert user.name == "john"
    assert user.email == "john@xconn.io"
    assert user.age == 35
    assert not user.isAdmin

    session.leave()


def test_pubsub_capnproto():
    session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    session.set_payload_codec(CapnpProtoCodec())

    def event_handler(event: Event):
        user: UserCreate = event.args[0]
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
