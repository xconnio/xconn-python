from dataclasses import dataclass

from xconn.types import WebsocketConfig


@dataclass
class ClientConfig:
    url: str
    realm: str
    authid: str
    authmethod: str
    schema_host: str
    schema_port: int
    websocket_config: WebsocketConfig = WebsocketConfig()

    secret: str = ""
    directory: str | None = None
