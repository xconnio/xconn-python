from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class RouterConfig(BaseModel):
    version: str
    realms: list[Realm]
    transports: list[Transport]
    authenticators: Authenticators


class Realm(BaseModel):
    name: str


class Serializers(str, Enum):
    json = "json"
    cbor = "cbor"
    msgpack = "msgpack"


class Transport(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    type: str
    host: str
    port: int
    serializers: list[Serializers]


class Authenticators(BaseModel):
    cryptosign: list[CryptoSign]
    wampcra: list[WAMPCRA]
    ticket: list[Ticket]
    anonymous: list[Anonymous]


class CryptoSign(BaseModel):
    authid: str
    realm: str
    role: str
    authorized_keys: list[str]


class WAMPCRA(BaseModel):
    authid: str
    realm: str
    role: str
    secret: str
    salt: str | None = None
    iterations: int | None = None
    keylen: int | None = None


class Ticket(BaseModel):
    authid: str
    realm: str
    role: str
    ticket: str


class Anonymous(BaseModel):
    authid: str
    realm: str
    role: str
