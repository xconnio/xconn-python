from asyncio import Future
from dataclasses import dataclass
from typing import Callable

from simple_websocket import Client
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


class BaseSession:
    def __init__(self, ws: Client, session_details: joiner.SessionDetails, serializer: serializers.Serializer):
        super().__init__()
        self.ws = ws
        self.session_details = session_details
        self.serializer = serializer

    def send(self, data: bytes):
        self.ws.send(data)

    def receive(self) -> bytes:
        return self.ws.receive()
