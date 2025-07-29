from __future__ import annotations

import asyncio
import contextlib
import inspect
from asyncio import Future
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Awaitable

from aiohttp import web
from wampproto import messages, joiner, serializers


@dataclass
class UnregisterRequest:
    future: Future
    registration_id: int


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


@dataclass
class WebsocketConfig:
    # max wait time for connection to be established
    open_timeout: float | None = 10

    # send ping automatically after every x seconds
    ping_interval: float | None = 20

    # wait for x seconds for a pong from server before closing the connection
    ping_timeout: float | None = 20

    # max wait time for closing the connection
    close_timeout: float | None = 10


class ITransport:
    def read(self) -> str | bytes:
        raise NotImplementedError()

    def write(self, data: str | bytes):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def is_connected(self) -> bool:
        raise NotImplementedError()

    def ping(self, timeout: int = 10) -> float:
        raise NotImplementedError()


class IAsyncTransport:
    async def read(self) -> str | bytes:
        raise NotImplementedError()

    async def write(self, data: str | bytes):
        raise NotImplementedError()

    async def close(self):
        raise NotImplementedError()

    async def is_connected(self) -> bool:
        raise NotImplementedError()

    async def ping(self, timeout: int = 10) -> float:
        raise NotImplementedError()


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
    def transport(self) -> ITransport:
        raise NotImplementedError()

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
    def __init__(
        self, transport: ITransport, session_details: joiner.SessionDetails, serializer: serializers.Serializer
    ):
        super().__init__()
        self._transport = transport
        self.session_details = session_details
        self.serializer = serializer

    @property
    def transport(self) -> ITransport:
        return self._transport

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
        self._transport.write(data)

    def receive(self) -> bytes:
        return self._transport.read()

    def send_message(self, msg: messages.Message):
        self.send(self.serializer.serialize(msg))

    def receive_message(self) -> messages.Message:
        return self.serializer.deserialize(self.receive())

    def close(self):
        self._transport.close()


class IAsyncBaseSession:
    @property
    def transport(self) -> IAsyncTransport:
        raise NotImplementedError()

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


class AsyncBaseSession(IAsyncBaseSession):
    def __init__(
        self, transport: IAsyncTransport, session_details: joiner.SessionDetails, serializer: serializers.Serializer
    ):
        super().__init__()
        self._transport = transport
        self.session_details = session_details
        self._serializer = serializer

    @property
    def transport(self) -> IAsyncTransport:
        return self._transport

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
        return await self._transport.write(data)

    async def receive(self) -> bytes:
        return await self._transport.read()

    async def send_message(self, msg: messages.Message):
        await self.send(self.serializer.serialize(msg))

    async def receive_message(self) -> messages.Message:
        return self.serializer.deserialize(await self.receive())

    async def close(self):
        await self._transport.close()


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


class _IncomingDetails(dict):
    def __init__(self, details: dict | None = None):
        super().__init__()
        if details:
            for k, v in details.items():
                self[k] = v


class CallDetails(_IncomingDetails):
    def __init__(self, details: dict | None = None):
        super().__init__(details)

    @property
    def session_id(self) -> int | None:
        return self.get("caller")

    @property
    def authid(self) -> str | None:
        return self.get("caller_authid")

    @property
    def authrole(self) -> str | None:
        return self.get("caller_authrole")


class EventDetails(_IncomingDetails):
    def __init__(self, details: dict | None = None):
        super().__init__(details)

    @property
    def session_id(self) -> int | None:
        return self.get("publisher")

    @property
    def authid(self) -> str | None:
        return self.get("publisher_authid")

    @property
    def authrole(self) -> str | None:
        return self.get("publisher_authrole")


class InvokeOptions(Enum):
    SINGLE = "single"
    ROUNDROBIN = "roundrobin"
    RANDOM = "random"
    FIRST = "first"
    LAST = "last"


class MatchOptions(Enum):
    EXACT = "exact"
    PREFIX = "prefix"
    WILDCARD = "wildcard"


class RegisterOptions(dict):
    def __init__(self, invoke: InvokeOptions = None, match: MatchOptions = None, concurrency: int = None, **kwargs):
        super().__init__()
        if invoke is not None:
            if not isinstance(invoke, InvokeOptions):
                raise ValueError("expected InvokeOptions for 'invoke' WAMP option")

            self["invoke"] = invoke.value
        if match is not None:
            if not isinstance(match, MatchOptions):
                raise ValueError("expected MatchOptions for 'match' WAMP option")

            self["match"] = match.value

        if concurrency is not None:
            if not isinstance(concurrency, int):
                raise ValueError("expected int for 'concurrency' WAMP option")

            self["concurrency"] = concurrency

        for k, v in kwargs.items():
            self[k] = v


class SubscribeOptions(dict):
    def __init__(self, match: MatchOptions = None, **kwargs):
        super().__init__()
        if match is not None:
            if not isinstance(match, MatchOptions):
                raise ValueError("expected MatchOptions for 'match' WAMP option")

            self["match"] = match.value

        for k, v in kwargs.items():
            self[k] = v


class CallOptions(dict):
    def __init__(self, timeout: int = None, disclose_me: bool | None = None, **kwargs):
        super().__init__()
        if timeout is not None:
            if not isinstance(timeout, int):
                raise ValueError("expected int for 'timeout' WAMP option")

            self["timeout"] = timeout

        if disclose_me is not None:
            if not isinstance(disclose_me, bool):
                raise ValueError("expected bool for 'disclose_me' WAMP option")

            self["disclose_me"] = disclose_me

        for k, v in kwargs.items():
            self[k] = v


class PublishOptions(dict):
    def __init__(
        self,
        acknowledge: bool | None = None,
        exclude_me: bool | None = None,
        disclose_me: bool | None = None,
        exclude: list[int] | None = None,
        eligible: list[int] | None = None,
        exclude_authid: list[int] | None = None,
        eligible_authid: list[int] | None = None,
        exclude_authrole: list[int] | None = None,
        eligible_authrole: list[int] | None = None,
        **kwargs,
    ):
        super().__init__()
        if acknowledge is not None:
            if not isinstance(acknowledge, bool):
                raise ValueError("expected bool for 'acknowledge' WAMP option")

            self["acknowledge"] = acknowledge

        if exclude_me is not None:
            if not isinstance(exclude_me, bool):
                raise ValueError("expected bool for 'exclude_me' WAMP option")

            self["exclude_me"] = exclude_me

        if disclose_me is not None:
            if not isinstance(disclose_me, bool):
                raise ValueError("expected bool for 'disclose_me' WAMP option")

            self["disclose_me"] = disclose_me

        if exclude is not None:
            if not isinstance(exclude, list):
                raise ValueError("expected list for 'exclude' WAMP option")

            self["exclude"] = exclude

        if eligible is not None:
            if not isinstance(eligible, list):
                raise ValueError("expected list for 'eligible' WAMP option")

            self["eligible"] = eligible

        if exclude_authid is not None:
            if not isinstance(exclude_authid, list):
                raise ValueError("expected list for 'exclude_authid' WAMP option")

            self["exclude_authid"] = exclude_authid

        if eligible_authid is not None:
            if not isinstance(eligible_authid, list):
                raise ValueError("expected list for 'eligible_authid' WAMP option")

            self["eligible_authid"] = eligible_authid

        if exclude_authrole is not None:
            if not isinstance(exclude_authrole, list):
                raise ValueError("expected list for 'exclude_authrole' WAMP option")

            self["exclude_authrole"] = exclude_authrole

        if eligible_authrole is not None:
            if not isinstance(eligible_authrole, list):
                raise ValueError("expected list for 'eligible_authrole' WAMP option")

            self["eligible_authrole"] = eligible_authrole

        for k, v in kwargs.items():
            self[k] = v


class Depends:
    def __init__(self, dependency: Callable | Awaitable):
        self._is_async = False
        self._is_async_gen = False

        self.dependency = self._setup(dependency)

    @property
    def is_async(self) -> bool:
        return self._is_async

    @property
    def is_async_gen(self) -> bool:
        return self._is_async_gen

    def _setup(self, func: Callable | Awaitable):
        if inspect.iscoroutinefunction(func):
            self._is_async = True
        elif inspect.isasyncgenfunction(func):
            self._is_async_gen = True
            return contextlib.asynccontextmanager(func)

        return func
