import re
import asyncio
import binascii
from typing import Any

from xconn import Server
from xconn._router import types
from xconn._router.exception import ValidationError
from xconn._router.types import RouterConfig, Authenticators


def is_valid_uri(uri: str) -> bool:
    uri_regex = re.compile(r"^([^\s.#]+\.)*([^\s.#]+)$")
    return bool(uri_regex.fullmatch(uri))


def validate_realms(realms: list[types.Realm]) -> None:
    for realm in realms:
        if not is_valid_uri(realm.name):
            raise ValidationError(f"invalid realm name: '{realm.name}'")


def validate_non_empty_no_space_string(field: str, field_name: str) -> None:
    if not field.strip():
        raise ValidationError(f"{field_name} is required")
    if " " in field:
        raise ValidationError(f"{field_name} must not contain empty spaces")


def validate_common_fields(authid: str, realm: str, role: str) -> None:
    validate_non_empty_no_space_string(authid, "authid")

    if not is_valid_uri(realm):
        raise ValidationError(f"invalid realm {realm}: must be a valid URI")

    validate_non_empty_no_space_string(role, "role")


def validate_authorized_keys(authorized_keys: list[str]) -> None:
    if len(authorized_keys) == 0:
        raise ValidationError("no authorized keys provided")
    for pub_key in authorized_keys:
        try:
            public_key_raw = binascii.unhexlify(pub_key)
        except binascii.Error as e:
            raise ValidationError(f"invalid public key: {e}") from e

        if len(public_key_raw) != 32:
            raise ValidationError("invalid public key: public key must have length of 32")


def validate_authenticators(authenticators: Authenticators) -> None:
    for auth in authenticators.anonymous:
        validate_common_fields(auth.authid, auth.realm, auth.role)

    for auth in authenticators.ticket:
        validate_common_fields(auth.authid, auth.realm, auth.role)

    for auth in authenticators.wampcra:
        validate_common_fields(auth.authid, auth.realm, auth.role)

    for auth in authenticators.cryptosign:
        validate_common_fields(auth.authid, auth.realm, auth.role)
        validate_authorized_keys(auth.authorized_keys)


def validate_config(data: dict[str, Any]) -> RouterConfig:
    config = RouterConfig(**data)
    validate_realms(config.realms)

    validate_authenticators(config.authenticators)

    return config


def start_server_sync(server: Server, transport: types.Transport) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.start(transport.host, transport.port))
    loop.run_forever()
