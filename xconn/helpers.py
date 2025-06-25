from wampproto import serializers
from wampproto.messages import Error
from wampproto.transports.rawsocket import SERIALIZER_TYPE_JSON, SERIALIZER_TYPE_MSGPACK, SERIALIZER_TYPE_CBOR

from xconn.exception import ApplicationError

JSON_SUBPROTOCOL = "wamp.2.json"
CBOR_SUBPROTOCOL = "wamp.2.cbor"
MSGPACK_SUBPROTOCOL = "wamp.2.msgpack"


def get_ws_subprotocol(serializer: serializers.Serializer):
    if isinstance(serializer, serializers.JSONSerializer):
        return JSON_SUBPROTOCOL
    elif isinstance(serializer, serializers.CBORSerializer):
        return CBOR_SUBPROTOCOL
    elif isinstance(serializer, serializers.MsgPackSerializer):
        return MSGPACK_SUBPROTOCOL
    else:
        raise ValueError("invalid serializer")


def get_rs_protocol(serializer: serializers.Serializer):
    if isinstance(serializer, serializers.JSONSerializer):
        return SERIALIZER_TYPE_JSON
    elif isinstance(serializer, serializers.CBORSerializer):
        return SERIALIZER_TYPE_CBOR
    elif isinstance(serializer, serializers.MsgPackSerializer):
        return SERIALIZER_TYPE_MSGPACK
    else:
        raise ValueError("invalid serializer")


def get_serializer(ws_subprotocol: str) -> serializers.Serializer:
    if ws_subprotocol == JSON_SUBPROTOCOL:
        return serializers.JSONSerializer()
    elif ws_subprotocol == CBOR_SUBPROTOCOL:
        return serializers.CBORSerializer()
    elif ws_subprotocol == MSGPACK_SUBPROTOCOL:
        return serializers.MsgPackSerializer()
    else:
        raise ValueError(f"invalid websocket subprotocol {ws_subprotocol}")


def exception_from_error(error: Error):
    exc = ApplicationError(error.uri)
    if error.args:
        exc.args = error.args
    if error.kwargs:
        exc.kwargs = error.kwargs

    return exc
