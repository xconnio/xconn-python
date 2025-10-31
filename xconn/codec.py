from typing import Generic, Type, TypeVar

from xconn.types import IncomingDataMessage, OutgoingDataMessage

T = TypeVar("T")


class Codec(Generic[T]):
    def name(self) -> str:
        raise NotImplementedError

    def encode(self, obj: T) -> OutgoingDataMessage:
        """Serialize a Python object to bytes."""
        raise NotImplementedError

    def decode(self, msg: IncomingDataMessage, out_type: Type[T]) -> T:
        """Deserialize the incoming message into an instance of out_type."""
        raise NotImplementedError
