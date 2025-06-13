import asyncio
import socket
from asyncio import StreamReader, StreamWriter
from typing import Sequence

from wampproto.transports.rawsocket import (
    Handshake,
    MessageHeader,
    DEFAULT_MAX_MSG_SIZE,
    SERIALIZER_TYPE_CBOR,
    MSG_TYPE_WAMP,
)
from websockets import State, Subprotocol
from websockets.sync.client import connect
from websockets.sync.connection import Connection
from websockets.asyncio.client import connect as async_connect
from websockets.asyncio.client import ClientConnection

from xconn.types import IAsyncTransport, ITransport, WebsocketConfig

# Applies to handshake and message itself.
RAW_SOCKET_HEADER_LENGTH = 4


class RawSocketTransport(ITransport):
    def __init__(self, sock: socket.socket):
        super().__init__()
        self._sock = sock

    @staticmethod
    def connect(
        host: str, port: int, protocol: int = SERIALIZER_TYPE_CBOR, max_msg_size: int = DEFAULT_MAX_MSG_SIZE
    ) -> "RawSocketTransport":
        sock = socket.create_connection((host, port))

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

        msg_payload_bytes = self._sock.recv(msg_header.length)
        return msg_payload_bytes

    def write(self, data: str | bytes):
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(data))

        self._sock.sendall(msg_header.to_bytes())
        self._sock.sendall(data)

    def close(self):
        self._sock.close()

    def is_connected(self) -> bool:
        try:
            self._sock.send(b"")  # Send zero bytes
            return True
        except (BrokenPipeError, ConnectionResetError, OSError):
            return False

    def ping(self, data: str | bytes | None = None) -> None:
        raise NotImplementedError()


class AsyncRawSocketTransport(IAsyncTransport):
    def __init__(self, reader: StreamReader, writer: StreamWriter):
        super().__init__()
        self._reader = reader
        self._writer = writer

    @staticmethod
    async def connect(
        host: str, port: int, protocol: int = SERIALIZER_TYPE_CBOR, max_msg_size: int = DEFAULT_MAX_MSG_SIZE
    ) -> "AsyncRawSocketTransport":
        reader, writer = await asyncio.open_connection(host, port)

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

        return await self._reader.read(msg_header.length)

    async def write(self, data: str | bytes):
        msg_header = MessageHeader(MSG_TYPE_WAMP, len(data))

        self._writer.write(msg_header.to_bytes())
        await self._writer.drain()
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

    def ping(self, data: str | bytes | None = None) -> None:
        raise NotImplementedError()


class WebSocketTransport(ITransport):
    def __init__(self, websocket: Connection):
        super().__init__()
        self._websocket = websocket

    @staticmethod
    def connect(uri: str, subprotocols: Sequence[Subprotocol], config: WebsocketConfig) -> "WebSocketTransport":
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

    def ping(self, data: str | bytes | None = None) -> None:
        return self._websocket.ping(data)


class AsyncWebSocketTransport(IAsyncTransport):
    def __init__(self, websocket: ClientConnection):
        super().__init__()
        self._websocket = websocket

    @staticmethod
    async def connect(
        uri: str, subprotocols: Sequence[Subprotocol], config: WebsocketConfig
    ) -> "AsyncWebSocketTransport":
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

    async def ping(self, data: str | bytes | None = None) -> None:
        await self._websocket.ping(data)
