import json
import inspect
from typing import Any, List as TypedList, Dict as TypingDict


class Value:
    def __init__(self, data: Any):
        self.data = data

    def raw(self) -> Any:
        return self.data

    def string(self) -> str:
        if isinstance(self.data, str):
            return self.data

        raise TypeError(f"value is not data string, got {type(self.data).__name__}")

    def string_or(self, default: str) -> str:
        try:
            return self.string()
        except TypeError:
            return default

    def bool_(self) -> bool:
        if isinstance(self.data, bool):
            return self.data

        raise TypeError(f"value is not data bool, got {type(self.data).__name__}")

    def bool_or(self, default: bool) -> bool:
        try:
            return self.bool_()
        except TypeError:
            return default

    def float_(self) -> float:
        if isinstance(self.data, (int, float)):
            return float(self.data)

        raise TypeError(f"value cannot be converted to float, got {type(self.data).__name__}")

    def float_or(self, default: float) -> float:
        try:
            return self.float_()
        except TypeError:
            return default

    def bytes_(self) -> bytes:
        if isinstance(self.data, bytes):
            return self.data
        if isinstance(self.data, str):
            return self.data.encode()
        raise TypeError(f"value cannot be converted to bytes, got {type(self.data).__name__}")

    def bytes_or(self, default: bytes) -> bytes:
        try:
            return self.bytes_()
        except TypeError:
            return default

    def decode(self, out_type: Any) -> Any:
        try:
            serialized = json.dumps(self.data)
            return json.loads(serialized, object_hook=out_type)
        except Exception as e:
            raise ValueError(f"failed to decode value: {e}")

    def list(self) -> TypedList[Any]:
        if isinstance(self.data, list):
            return self.data

        raise TypeError(f"value is not data list, got {type(self.data).__name__}")

    def list_or(self, default: TypedList[Any]) -> TypedList[Any]:
        try:
            return self.list()
        except TypeError:
            return default


class List:
    def __init__(self, values: TypedList[Any]):
        self.values: TypedList[Value] = [Value(v) for v in values]

    def __len__(self) -> int:
        return len(self.values)

    def get(self, i: int) -> Value:
        if 0 <= i < len(self.values):
            return self.values[i]

        raise IndexError(f"index {i} out of range [0, {len(self.values)})")

    def get_or(self, i: int, default: Any) -> Value:
        try:
            return self.get(i)
        except IndexError:
            return Value(default)

    def string(self, i: int) -> str:
        return self.get(i).string()

    def string_or(self, i: int, default: str) -> str:
        return self.get_or(i, default).string_or(default)

    def bool_(self, i: int) -> bool:
        return self.get(i).bool_()

    def bool_or(self, i: int, default: bool) -> bool:
        return self.get_or(i, default).bool_or(default)

    def float_(self, i: int) -> float:
        return self.get(i).float_()

    def float_or(self, i: int, default: float) -> float:
        return self.get_or(i, default).float_or(default)

    def bytes_(self, i: int) -> bytes:
        return self.get(i).bytes_()

    def bytes_or(self, i: int, default: bytes) -> bytes:
        return self.get_or(i, default).bytes_or(default)

    def decode(self, out_type: Any) -> Any:
        raw_values = [v.raw() for v in self.values]

        if not inspect.isclass(out_type):
            raise TypeError("out_type must be a class")

        try:
            serialized = json.dumps(raw_values)
            return json.loads(serialized, object_hook=lambda d: out_type(**d))
        except Exception as e:
            raise ValueError(f"failed to decode list: {e}")

    def list(self, i: int) -> TypedList[Any]:
        return self.get(i).list()

    def list_or(self, i: int, default: TypedList[Any]) -> TypedList[Any]:
        return self.get_or(i, default).list_or(default)

    def raw(self) -> TypedList[Any]:
        return [v.raw() for v in self.values]


class Dict:
    def __init__(self, values: TypingDict[str, Any]):
        self.values: TypingDict[str, Value] = {k: Value(v) for k, v in values.items()}

    def __len__(self) -> int:
        return len(self.values)

    def has(self, key: str) -> bool:
        return key in self.values

    def get(self, key: str) -> Value:
        if key in self.values:
            return self.values[key]

        raise KeyError(f"key '{key}' not found")

    def get_or(self, key: str, default: Any) -> Value:
        return self.values.get(key, Value(default))

    def string(self, key: str) -> str:
        return self.get(key).string()

    def string_or(self, key: str, default: str) -> str:
        return self.get_or(key, default).string_or(default)

    def bool_(self, key: str) -> bool:
        return self.get(key).bool_()

    def bool_or(self, key: str, default: bool) -> bool:
        return self.get_or(key, default).bool_or(default)

    def float_(self, key: str) -> float:
        return self.get(key).float_()

    def float_or(self, key: str, default: float) -> float:
        return self.get_or(key, default).float_or(default)

    def bytes_(self, key: str) -> bytes:
        return self.get(key).bytes_()

    def bytes_or(self, key: str, default: bytes) -> bytes:
        return self.get_or(key, default).bytes_or(default)

    def raw(self) -> TypingDict[str, Any]:
        return {k: v.raw() for k, v in self.values.items()}

    def decode(self, out_type: Any) -> Any:
        try:
            serialized = json.dumps(self.raw())
            if not inspect.isclass(out_type):
                raise TypeError("out_type must be a class")

            return json.loads(serialized, object_hook=lambda d: out_type(**d))
        except Exception as e:
            raise ValueError(f"failed to decode dict into structure: {e}")
