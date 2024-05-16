from __future__ import annotations

import asyncio
from asyncio import Future
from collections import deque
from dataclasses import dataclass
from typing import Callable

from aiohttp import web
from websockets.sync.connection import Connection
from wampproto import messages, joiner, serializers


@dataclass
class Registration:
    registration_id: int


@dataclass
class RegisterRequest:
    future: Future[Registration]
    endpoint: Callable[[Invocation], Result]


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
    endpoint: Callable[[Event], None]


@dataclass
class UnsubscribeRequest:
    future: Future
    subscription_id: int


@dataclass
class Result:
    args: list | None = None
    kwargs: dict | None = None
    details: dict | None = None


@dataclass
class Invocation:
    args: list | None
    kwargs: dict | None
    details: dict | None


@dataclass
class Event:
    args: list | None
    kwargs: dict | None
    details: dict | None


class IBasePeer:
    def read(self) -> str | bytes:
        raise NotImplementedError()

    def write(self, data: str | bytes):
        raise NotImplementedError()


class BasePeer(IBasePeer):
    def read(self) -> str | bytes:
        return super().read()

    def write(self, data: str | bytes):
        super().write(data)


class IPeer:
    def read(self) -> str | bytes:
        raise NotImplementedError()

    def write(self, data: str | bytes):
        raise NotImplementedError()

    def read_message(self) -> messages.Message:
        raise NotImplementedError()

    def write_message(self, msg: messages.Message):
        raise NotImplementedError()


class Peer(IPeer):
    def __init__(self, base_peer: BasePeer):
        super().__init__()
        self._base_peer = base_peer


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

    def close(self):
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

    def close(self):
        self.ws.close()


class IAsyncBaseSession:
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

    @property
    def serializer(self) -> serializers.Serializer:
        raise NotImplementedError()

    async def send(self, data: bytes | str):
        raise NotImplementedError()

    async def receive(self) -> bytes | str:
        raise NotImplementedError()

    async def send_message(self, msg: messages.Message):
        raise NotImplementedError()

    async def receive_message(self) -> messages.Message:
        raise NotImplementedError()

    async def close(self):
        raise NotImplementedError()


class AIOHttpBaseSession(IAsyncBaseSession):
    def __init__(
        self, ws: web.WebSocketResponse, session_details: joiner.SessionDetails, serializer: serializers.Serializer
    ):
        super().__init__()
        self.ws = ws
        self.session_details = session_details
        self._serializer = serializer
        if serializer is None or isinstance(serializer, serializers.JSONSerializer):
            self._send_func = ws.send_str
            self._receive_func = ws.receive_str
        else:
            self._send_func = ws.send_bytes
            self._receive_func = ws.receive_bytes

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

    @property
    def serializer(self) -> serializers.Serializer:
        return self._serializer

    async def send(self, data: bytes):
        await self._send_func(data)

    async def receive(self) -> bytes:
        return await self._receive_func()

    async def send_message(self, msg: messages.Message):
        await self.send(self.serializer.serialize(msg))

    async def receive_message(self) -> messages.Message:
        return self.serializer.deserialize(await self.receive())

    async def close(self):
        await self.ws.close()


class ClientSideLocalBaseSession(IAsyncBaseSession):
    def __init__(self, sid: int, realm: str, authid: str, authrole: str, serializer: serializers.Serializer, router):
        super().__init__()
        self._sid: int = sid
        self._realm: str = realm
        self._authid: str = authid
        self._authrole: str = authrole
        self._serializer: serializers.Serializer = serializer
        self._router = router

        self._incoming_messages = deque()
        self._cond = asyncio.Condition()

    @property
    def id(self) -> int:
        return self._sid

    @property
    def realm(self) -> str:
        return self._realm

    @property
    def authid(self) -> str:
        return self._authid

    @property
    def authrole(self) -> str:
        return self._authrole

    @property
    def serializer(self) -> serializers.Serializer:
        return self._serializer

    async def send(self, data: bytes | str):
        await self.send_message(self.serializer.deserialize(data))

    async def receive(self) -> bytes | str:
        async with self._cond:
            while not self._incoming_messages:
                await self._cond.wait()

            return self._incoming_messages.popleft()

    async def send_message(self, msg: messages.Message):
        await self._router.receive_message(self, msg)

    async def receive_message(self) -> messages.Message:
        return self.serializer.deserialize(await self.receive())

    async def close(self):
        pass

    async def feed(self, data: bytes | str):
        async with self._cond:
            self._incoming_messages.append(data)
            self._cond.notify()


class ServerSideLocalBaseSession(IAsyncBaseSession):
    def __init__(self, sid: int, realm: str, authid: str, authrole: str, serializer: serializers.Serializer):
        super().__init__()
        self._sid: int = sid
        self._realm: str = realm
        self._authid: str = authid
        self._authrole: str = authrole
        self._serializer: serializers.Serializer = serializer
        self._other: ClientSideLocalBaseSession = None

    def set_other(self, other: ClientSideLocalBaseSession):
        self._other = other

    @property
    def id(self) -> int:
        return self._sid

    @property
    def realm(self) -> str:
        return self._realm

    @property
    def authid(self) -> str:
        return self._authid

    @property
    def authrole(self) -> str:
        return self._authrole

    @property
    def serializer(self) -> serializers.Serializer:
        return self._serializer

    async def send(self, data: bytes | str):
        await self._other.feed(data)

    async def send_message(self, msg: messages.Message):
        await self.send(self.serializer.serialize(msg))

    async def close(self):
        pass
