from asyncio import Future
from dataclasses import dataclass
from typing import Callable

from websockets.sync.connection import Connection
from wampproto import messages, joiner, serializers


@dataclass
class Registration:
    registration_id: int


@dataclass
class RegisterRequest:
    future: Future[Registration]
    endpoint: Callable[[messages.Invocation], messages.Yield]


@dataclass
class UnregisterRequest:
    future: Future
    registration_id: int


@dataclass
class Subscription:
    subscription_id: int


@dataclass
class SubscribeRequest:
    future: Future[Subscription]
    endpoint: Callable[[messages.Event], None]


@dataclass
class UnsubscribeRequest:
    future: Future[messages.UnSubscribed]
    subscription_id: int


class IBaseSession:
    @property
    def id(self) -> int:
        raise NotImplementedError()

    @property
    def realm(self) -> str:
        raise NotImplementedError()

    @property
    def authid(self) -> str:
        raise NotImplementedError()

    @property
    def authrole(self) -> str:
        raise NotImplementedError()

    def send(self, data: bytes):
        raise NotImplementedError()

    def receive(self) -> bytes:
        raise NotImplementedError()

    def send_message(self, msg: messages.Message):
        raise NotImplementedError()

    def receive_message(self) -> messages.Message:
        raise NotImplementedError()


class BaseSession(IBaseSession):
    def __init__(self, ws: Connection, session_details: joiner.SessionDetails, serializer: serializers.Serializer):
        super().__init__()
        self.ws = ws
        self.session_details = session_details
        self.serializer = serializer

    @property
    def id(self) -> int:
        return self.session_details.session_id

    @property
    def realm(self) -> str:
        return self.session_details.realm

    @property
    def authid(self) -> str:
        return self.session_details.authid

    @property
    def authrole(self) -> str:
        return self.session_details.authrole

    def send(self, data: bytes):
        self.ws.send(data)

    def receive(self) -> bytes:
        return self.ws.recv()

    def send_message(self, msg: messages.Message):
        self.ws.send(self.serializer.serialize(msg))

    def receive_message(self) -> messages.Message:
        return self.serializer.deserialize(self.receive())
