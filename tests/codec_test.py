import base64
from typing import Type

from xconn.client import connect_anonymous
from xconn import codec


class String(str):
    pass


class Base64Codec(codec.Codec[String]):
    def name(self) -> str:
        return "base64"

    def encode(self, obj: String) -> str:
        return base64.b64encode(obj.encode("utf-8")).decode("utf-8")

    def decode(self, data: str, out_type: Type[String]) -> String:
        return out_type(base64.b64decode(data.encode("utf-8")).decode())


def test_base64_codec():
    encoder = Base64Codec()
    encoded = encoder.encode(String("hello"))
    assert isinstance(encoded, str)

    decoded = encoder.decode(encoded, String)
    assert isinstance(decoded, String)
    assert decoded == "hello"


def test_something():
    # session = connect_anonymous("ws://localhost:8080/ws", "realm1")
    # session.set_payload_codec(Base64Codec())
    # result = session.call_object("io.xconn.object", String("hello"), String)
    # print(result)
    # session.leave()
    pass
