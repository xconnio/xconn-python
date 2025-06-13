import asyncio
import socket
from asyncio import StreamReader, StreamWriter

from wampproto.transports.rawsocket import (
    Handshake,
    MessageHeader,
    DEFAULT_MAX_MSG_SIZE,
    SERIALIZER_TYPE_CBOR,
    MSG_TYPE_WAMP,
)

from xconn.types import IAsyncTransport, ITransport

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
