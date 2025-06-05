import re

from xconn._router import types


def is_valid_uri(uri: str) -> bool:
    uri_regex = re.compile(r"^([^\s.#]+\.)*([^\s.#]+)$")
    return bool(uri_regex.fullmatch(uri))


def validate_realms(realms: list[types.Realm]):
    for realm in realms:
        if not is_valid_uri(realm.name):
            raise ValueError(f"invalid realm name: '{realm.name}'")


def validate_transport(transport: types.Transport):
    if transport.type != "websocket":
        raise TypeError("type is required and must be 'websocket'")
    pass
