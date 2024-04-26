from wampproto import serializers

from wamp.wsjoiner import WAMPSessionJoiner


def get_ws_subprotocol(serializer: serializers.Serializer):
    if isinstance(serializer, serializers.JSONSerializer):
        return WAMPSessionJoiner.JSON_SUBPROTOCOL
    elif isinstance(serializer, serializers.CBORSerializer):
        return WAMPSessionJoiner.CBOR_SUBPROTOCOL
    elif isinstance(serializer, serializers.MsgPackSerializer):
        return WAMPSessionJoiner.MSGPACK_SUBPROTOCOL
    else:
        raise ValueError("invalid serializer")
