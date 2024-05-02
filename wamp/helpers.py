from wampproto import serializers

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
