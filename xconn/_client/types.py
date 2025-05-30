from dataclasses import dataclass


@dataclass
class ClientConfig:
    url: str
    realm: str
    authid: str
    authmethod: str
    schema_host: str
    schema_port: int

    secret: str = ""
    directory: str | None = None
