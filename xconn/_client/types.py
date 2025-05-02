from dataclasses import dataclass


@dataclass
class ClientConfig:
    url: str
    realm: str
    authid: str
    authmethod: str

    secret: str | None = None
    directory: str | None = None
