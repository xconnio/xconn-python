from asyncio import Future
from dataclasses import dataclass
from typing import Callable

from wampproto import messages


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
