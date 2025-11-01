import asyncio
import os
import socket
from asyncio import StreamReader, StreamWriter, Future
from concurrent.futures import Future as ConcurrentFuture
from dataclasses import dataclass
import time
from typing import Sequence
import threading
from urllib.parse import urlparse

from wampproto.transports.rawsocket import (
    Handshake,
    MessageHeader,
    DEFAULT_MAX_MSG_SIZE,
    SERIALIZER_TYPE_CBOR,
    MSG_TYPE_WAMP,
    MSG_TYPE_PING,
    MSG_TYPE_PONG,
)
from websockets import State, Subprotocol
from websockets.sync.client import connect, unix_connect
from websockets.sync.connection import Connection
from websockets.asyncio.client import connect as async_connect, unix_connect as async_unix_connect
from websockets.asyncio.client import ClientConnection

from xconn.types import IAsyncTransport, ITransport, WebsocketConfig, TransportConfig

# Applies to handshake and message itself.
RAW_SOCKET_HEADER_LENGTH = 4

_ASYNC_CONNECTION_ERRORS = (
    asyncio.IncompleteReadError,
    BrokenPipeError,
    ConnectionResetError,
    OSError,
)

_CONNECTION_ERRORS = (
    BrokenPipeError,
    ConnectionResetError,
    OSError,
)


@dataclass
class PendingPing:
    future: Future[float] | ConcurrentFuture[float]
    created_at: float


def create_ping():
    payload = os.urandom(16)
    ping_header = MessageHeader(MSG_TYPE_PING, len(payload))
    created_at = time.time() * 1000

    return payload, ping_header, created_at


def _recv_exactly(sock, n: int) -> bytes:
    """Receive exactly n bytes from a socket or raise if connection breaks."""
    chunks = []
    received = 0
    while received < n:
        chunk = sock.recv(n - received)
        if not chunk:
            raise ConnectionError("Socket connection broken")

        chunks.append(chunk)
        received += len(chunk)

    return b"".join(chunks)


class RawSocketTransport(ITransport):
    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock = sock
        self._connected = True
        self._pending_pings: dict[bytes, PendingPing] = {}
        self._write_lock = threading.Lock()

    @staticmethod
    def connect(
        uri: str,
        protocol: int = SERIALIZER_TYPE_CBOR,
        max_msg_size: int = DEFAULT_MAX_MSG_SIZE,
        config: TransportConfig = TransportConfig(),
    ) -> "RawSocketTransport":
        parsed = urlparse(uri)

        if parsed.scheme == "rs" or parsed.scheme == "rss" or parsed.scheme == "tcp" or parsed.scheme == "tcps":
            sock = socket.create_connection((parsed.hostname, parsed.port))
            if config.tcp_nodelay:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        elif parsed.scheme == "unix" or parsed.scheme == "unix+rs":
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(parsed.path)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        hs_request = Handshake(protocol, max_msg_size)

        sock.sendall(hs_request.to_bytes())

        hs_response_bytes = _recv_exactly(sock, RAW_SOCKET_HEADER_LENGTH)
        hs_response = Handshake.from_bytes(hs_response_bytes)

        if hs_request.protocol != hs_response.protocol:
            raise ValueError("Handshake protocol mismatch.")

        return RawSocketTransport(sock)

    def _mark_disconnected(self, _: Exception | None):
        if self._connected:
            self._connected = False

    def read(self) -> str | bytes:
        msg_header_bytes = _recv_exactly(self._sock, RAW_SOCKET_HEADER_LENGTH)
        msg_header = MessageHeader.from_bytes(msg_header_bytes)

        if msg_header.kind == MSG_TYPE_WAMP:
            return _recv_exactly(self._sock, msg_header.length)
        elif msg_header.kind == MSG_TYPE_PING:
            ping_payload = _recv_exactly(self._sock, msg_header.length)
            pong_header = MessageHeader(MSG_TYPE_PONG, msg_header.length)

            try:
                with self._write_lock:
                    self._sock.sendall(pong_header.to_bytes() + ping_payload)
            except _CONNECTION_ERRORS as e:
                self._mark_disconnected(e)
                raise

            return self.read()
        elif msg_header.kind == MSG_TYPE_PONG:
            pong_payload = _recv_exactly(self._sock, msg_header.length)
            pending_ping = self._pending_pings.pop(pong_payload, None)
            if pending_ping is not None:
                received_at = time.time() * 1000
                pending_ping.future.set_result(received_at - pending_ping.created_at)

            return self.read()
        else:
            raise ValueError(f"Unsupported message type {msg_header.kind}")

    def write(self, data: str | bytes):
        payload = data.encode() if isinstance(data, str) else data
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(payload))

        try:
            with self._write_lock:
                self._sock.sendall(msg_header.to_bytes() + payload)
        except _CONNECTION_ERRORS as e:
            self._mark_disconnected(e)
            raise

    def close(self):
        try:
            self._sock.close()
        finally:
            self._mark_disconnected(None)

    def is_connected(self) -> bool:
        return self._connected

    def ping(self, timeout: int = 10) -> float:
        f: ConcurrentFuture[int] = ConcurrentFuture()
        payload, ping_header, created_at = create_ping()
        self._pending_pings[payload] = PendingPing(f, created_at)

        try:
            with self._write_lock:
                self._sock.sendall(ping_header.to_bytes() + payload)
        except _CONNECTION_ERRORS as e:
            self._mark_disconnected(e)
            raise

        return f.result(timeout)


class AsyncRawSocketTransport(IAsyncTransport):
    def __init__(self, reader: StreamReader, writer: StreamWriter):
        super().__init__()
        self._reader = reader
        self._writer = writer

        self._connected = True
        self._pending_pings: dict[bytes, PendingPing] = {}

    @staticmethod
    async def connect(
        uri: str,
        protocol: int = SERIALIZER_TYPE_CBOR,
        max_msg_size: int = DEFAULT_MAX_MSG_SIZE,
        config: TransportConfig = TransportConfig(),
    ) -> "AsyncRawSocketTransport":
        parsed = urlparse(uri)

        if parsed.scheme == "rs" or parsed.scheme == "rss" or parsed.scheme == "tcp" or parsed.scheme == "tcps":
            reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
            if config.tcp_nodelay and (sock := writer.get_extra_info("socket")):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        elif parsed.scheme == "unix" or parsed.scheme == "unix+rs":
            reader, writer = await asyncio.open_unix_connection(parsed.path)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        hs_request = Handshake(protocol, max_msg_size)

        writer.write(hs_request.to_bytes())
        await writer.drain()

        hs_response_bytes = await reader.readexactly(RAW_SOCKET_HEADER_LENGTH)
        hs_response = Handshake.from_bytes(hs_response_bytes)

        if hs_request.protocol != hs_response.protocol:
            raise ValueError("Handshake protocol mismatch.")

        return AsyncRawSocketTransport(reader, writer)

    def _mark_disconnected(self, _: Exception | None):
        if self._connected:
            self._connected = False

    async def read(self) -> str | bytes:
        try:
            msg_header_bytes = await self._reader.readexactly(RAW_SOCKET_HEADER_LENGTH)
        except _ASYNC_CONNECTION_ERRORS as e:
            self._mark_disconnected(e)
            raise

        msg_header = MessageHeader.from_bytes(msg_header_bytes)

        if msg_header.kind == MSG_TYPE_WAMP:
            try:
                return await self._reader.readexactly(msg_header.length)
            except _ASYNC_CONNECTION_ERRORS as e:
                self._mark_disconnected(e)
                raise
        elif msg_header.kind == MSG_TYPE_PING:
            try:
                ping_payload = await self._reader.readexactly(msg_header.length)
            except _ASYNC_CONNECTION_ERRORS as e:
                self._mark_disconnected(e)
                raise

            pong_header = MessageHeader(MSG_TYPE_PONG, msg_header.length)

            try:
                self._writer.write(pong_header.to_bytes() + ping_payload)
                await self._writer.drain()
            except _CONNECTION_ERRORS as e:
                self._mark_disconnected(e)
                raise

            return await self.read()
        elif msg_header.kind == MSG_TYPE_PONG:
            try:
                pong_payload = await self._reader.readexactly(msg_header.length)
            except _ASYNC_CONNECTION_ERRORS as e:
                self._mark_disconnected(e)
                raise

            pending_ping = self._pending_pings.pop(pong_payload, None)
            if pending_ping is not None:
                received_at = time.time() * 1000
                pending_ping.future.set_result(received_at - pending_ping.created_at)

            return await self.read()
        else:
            raise ValueError(f"Unsupported message type {msg_header.kind}")

    async def write(self, data: str | bytes):
        payload = data.encode() if isinstance(data, str) else data
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(payload))

        try:
            self._writer.write(msg_header.to_bytes() + payload)
            await self._writer.drain()
        except _CONNECTION_ERRORS as e:
            self._mark_disconnected(e)
            raise

    async def close(self):
        try:
            self._writer.close()
        finally:
            self._mark_disconnected(None)

    async def is_connected(self) -> bool:
        return self._connected

    async def ping(self, timeout: int = 10) -> float:
        f: Future[int] = Future()
        payload, ping_header, created_at = create_ping()
        self._pending_pings[payload] = PendingPing(f, created_at)

        try:
            self._writer.write(ping_header.to_bytes() + payload)
            await self._writer.drain()
        except _CONNECTION_ERRORS as e:
            self._mark_disconnected(e)
            raise

        return await asyncio.wait_for(f, timeout)


class WebSocketTransport(ITransport):
    def __init__(self, websocket: Connection):
        super().__init__()
        self._websocket = websocket

    @staticmethod
    def connect(uri: str, subprotocols: Sequence[Subprotocol], config: WebsocketConfig) -> "WebSocketTransport":
        parsed_url = urlparse(uri)
        if parsed_url.scheme == "unix+ws":
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(parsed_url.path)
            ws = unix_connect(
                parsed_url.path,
                subprotocols=subprotocols,
                open_timeout=config.open_timeout,
                ping_interval=config.ping_interval,
                ping_timeout=config.ping_timeout,
                close_timeout=config.close_timeout,
            )
        else:
            ws = connect(
                uri,
                subprotocols=subprotocols,
                open_timeout=config.open_timeout,
                ping_interval=config.ping_interval,
                ping_timeout=config.ping_timeout,
                close_timeout=config.close_timeout,
            )

        return WebSocketTransport(ws)

    def read(self) -> str | bytes:
        return self._websocket.recv()

    def write(self, data: str | bytes):
        self._websocket.send(data)

    def close(self):
        self._websocket.close()

    def is_connected(self) -> bool:
        return self._websocket.state == State.OPEN

    def ping(self, timeout: int = 10) -> float:
        payload, _, created_at = create_ping()

        event = self._websocket.ping(payload)
        event.wait(timeout)
        received_at = time.time() * 1000
        return received_at - created_at


class AsyncWebSocketTransport(IAsyncTransport):
    def __init__(self, websocket: ClientConnection):
        super().__init__()
        self._websocket = websocket

    @staticmethod
    async def connect(
        uri: str, subprotocols: Sequence[Subprotocol], config: WebsocketConfig
    ) -> "AsyncWebSocketTransport":
        parsed_url = urlparse(uri)
        if parsed_url.scheme == "unix+ws":
            ws = await async_unix_connect(
                parsed_url.path,
                subprotocols=subprotocols,
                open_timeout=config.open_timeout,
                ping_interval=config.ping_interval,
                ping_timeout=config.ping_timeout,
                close_timeout=config.close_timeout,
            )
        else:
            ws = await async_connect(
                uri,
                subprotocols=subprotocols,
                open_timeout=config.open_timeout,
                ping_interval=config.ping_interval,
                ping_timeout=config.ping_timeout,
                close_timeout=config.close_timeout,
            )

        return AsyncWebSocketTransport(ws)

    async def read(self) -> str | bytes:
        return await self._websocket.recv()

    async def write(self, data: str | bytes):
        await self._websocket.send(data)

    async def close(self):
        await self._websocket.close()

    async def is_connected(self) -> bool:
        return self._websocket.state == State.OPEN

    async def ping(self, timeout: int = 10) -> float:
        payload, _, created_at = create_ping()

        awaitable = await self._websocket.ping(payload)
        await asyncio.wait_for(awaitable, timeout)
        received_at = time.time() * 1000
        return received_at - created_at
