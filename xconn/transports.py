import asyncio
import os
import socket
from asyncio import StreamReader, StreamWriter, Future
from concurrent.futures import Future as ConcurrentFuture
from dataclasses import dataclass
import time
from typing import Sequence
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

from xconn.types import IAsyncTransport, ITransport, WebsocketConfig

# Applies to handshake and message itself.
RAW_SOCKET_HEADER_LENGTH = 4


@dataclass
class PendingPing:
    future: Future[float] | ConcurrentFuture[float]
    created_at: float


def create_ping():
    payload = os.urandom(16)
    ping_header = MessageHeader(MSG_TYPE_PING, len(payload))
    created_at = time.time() * 1000

    return payload, ping_header, created_at


class RawSocketTransport(ITransport):
    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock = sock

        self._pending_pings: dict[bytes, PendingPing] = {}

    @staticmethod
    def connect(
        uri: str, protocol: int = SERIALIZER_TYPE_CBOR, max_msg_size: int = DEFAULT_MAX_MSG_SIZE
    ) -> "RawSocketTransport":
        parsed = urlparse(uri)

        if parsed.scheme == "rs" or parsed.scheme == "rss" or parsed.scheme == "tcp" or parsed.scheme == "tcps":
            sock = socket.create_connection((parsed.hostname, parsed.port))
        elif parsed.scheme == "unix" or parsed.scheme == "unix+rs":
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(parsed.path)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        hs_request = Handshake(protocol, max_msg_size)

        sock.sendall(hs_request.to_bytes())

        hs_response_bytes = sock.recv(RAW_SOCKET_HEADER_LENGTH)
        hs_response = Handshake.from_bytes(hs_response_bytes)

        if hs_request.protocol != hs_response.protocol:
            raise ValueError("Handshake protocol mismatch.")

        return RawSocketTransport(sock)

    def read(self) -> str | bytes:
        msg_header_bytes = self._sock.recv(RAW_SOCKET_HEADER_LENGTH)
        msg_header = MessageHeader.from_bytes(msg_header_bytes)

        if msg_header.kind == MSG_TYPE_WAMP:
            return self._sock.recv(msg_header.length)
        elif msg_header.kind == MSG_TYPE_PING:
            ping_payload = self._sock.recv(msg_header.length)
            pong = MessageHeader(MSG_TYPE_PONG, msg_header.length)
            self._sock.sendall(pong.to_bytes())
            self._sock.sendall(ping_payload)

            return self.read()
        elif msg_header.kind == MSG_TYPE_PONG:
            pong_payload = self._sock.recv(msg_header.length)
            pending_ping = self._pending_pings.pop(pong_payload, None)
            if pending_ping is not None:
                received_at = time.time() * 1000
                pending_ping.future.set_result(received_at - pending_ping.created_at)

            return self.read()
        else:
            raise ValueError(f"Unsupported message type {msg_header.kind}")

    def write(self, data: str | bytes):
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(data))

        self._sock.sendall(msg_header.to_bytes())

        if isinstance(data, str):
            self._sock.sendall(data.encode())
        else:
            self._sock.sendall(data)

    def close(self):
        self._sock.close()

    def is_connected(self) -> bool:
        try:
            self._sock.send(b"")  # Send zero bytes
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def ping(self, timeout: int = 10) -> float:
        f: ConcurrentFuture[int] = ConcurrentFuture()
        payload, ping_header, created_at = create_ping()
        self._pending_pings[payload] = PendingPing(f, created_at)

        self._sock.sendall(ping_header.to_bytes())
        self._sock.sendall(payload)

        return f.result(timeout)


class AsyncRawSocketTransport(IAsyncTransport):
    def __init__(self, reader: StreamReader, writer: StreamWriter):
        super().__init__()
        self._reader = reader
        self._writer = writer

        self._pending_pings: dict[bytes, PendingPing] = {}

    @staticmethod
    async def connect(
        uri: str, protocol: int = SERIALIZER_TYPE_CBOR, max_msg_size: int = DEFAULT_MAX_MSG_SIZE
    ) -> "AsyncRawSocketTransport":
        parsed = urlparse(uri)

        if parsed.scheme == "rs" or parsed.scheme == "rss" or parsed.scheme == "tcp" or parsed.scheme == "tcps":
            reader, writer = await asyncio.open_connection(parsed.hostname, parsed.port)
        elif parsed.scheme == "unix" or parsed.scheme == "unix+rs":
            reader, writer = await asyncio.open_unix_connection(parsed.path)
        else:
            raise RuntimeError(f"Unsupported scheme {parsed.scheme}")

        hs_request = Handshake(protocol, max_msg_size)

        writer.write(hs_request.to_bytes())
        await writer.drain()

        hs_response_bytes = await reader.read(RAW_SOCKET_HEADER_LENGTH)
        hs_response = Handshake.from_bytes(hs_response_bytes)

        if hs_request.protocol != hs_response.protocol:
            raise ValueError("Handshake protocol mismatch.")

        return AsyncRawSocketTransport(reader, writer)

    async def read(self) -> str | bytes:
        msg_header_bytes = await self._reader.read(RAW_SOCKET_HEADER_LENGTH)
        msg_header = MessageHeader.from_bytes(msg_header_bytes)

        if msg_header.kind == MSG_TYPE_WAMP:
            return await self._reader.read(msg_header.length)
        elif msg_header.kind == MSG_TYPE_PING:
            ping_payload = await self._reader.read(msg_header.length)
            pong = MessageHeader(MSG_TYPE_PONG, msg_header.length)
            self._writer.write(pong.to_bytes())
            await self._writer.drain()
            self._writer.write(ping_payload)
            await self._writer.drain()

            return await self.read()
        elif msg_header.kind == MSG_TYPE_PONG:
            pong_payload = await self._reader.read(msg_header.length)
            pending_ping = self._pending_pings.pop(pong_payload, None)
            if pending_ping is not None:
                received_at = time.time() * 1000
                pending_ping.future.set_result(received_at - pending_ping.created_at)

            return await self.read()
        else:
            raise ValueError(f"Unsupported message type {msg_header.kind}")

    async def write(self, data: str | bytes):
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(data))

        self._writer.write(msg_header.to_bytes())
        await self._writer.drain()

        if isinstance(data, str):
            self._writer.write(data.encode())
        else:
            self._writer.write(data)

        await self._writer.drain()

    async def close(self):
        self._writer.close()

    async def is_connected(self) -> bool:
        try:
            self._writer.write(b"")  # Send zero bytes
            await self._writer.drain()
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    async def ping(self, timeout: int = 10) -> float:
        f: Future[int] = Future()
        payload, ping_header, created_at = create_ping()
        self._pending_pings[payload] = PendingPing(f, created_at)

        self._writer.write(ping_header.to_bytes())
        await self._writer.drain()

        self._writer.write(payload)
        await self._writer.drain()

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
