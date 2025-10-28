from typing import Any, Generic, Type, TypeVar

T = TypeVar("T")


class Codec(Generic[T]):
    def name(self) -> str:
        raise NotImplementedError

    def encode(self, obj: Any) -> bytes | str:
        """Serialize a Python object to bytes."""
        raise NotImplementedError

    def decode(self, data: bytes | str, out_type: Type[T]) -> T:
        """Deserialize bytes into an instance of out_type."""
        raise NotImplementedError
