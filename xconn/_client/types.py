from pydantic import BaseModel, Field

from xconn.types import WebsocketConfig


class ClientConfig(BaseModel):
    schema_host: str
    schema_port: int
    url: str
    realm: str
    websocket_config: WebsocketConfig = WebsocketConfig()

    authid: str | None = None
    authmethod: str | None = None
    secret: str | None = None
    ticket: str | None = None
    private_key: str | None = None


class CommandArgs(BaseModel):
    app: str = Field(alias="APP")
    url: str | None = None
    realm: str | None = None
    directory: str | None = None
    asyncio: bool
    schema_host: str
    schema_port: int
    no_config: bool
    start_router: bool = Field(alias="router")

    authid: str | None = None
    ticket: str | None = None
    secret: str | None = None
    private_key: str | None = None

    open_timeout: int
    ping_interval: int
    ping_timeout: int
