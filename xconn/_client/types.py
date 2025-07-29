import enum

from pydantic import BaseModel, Field

from xconn.types import WebsocketConfig


class ConfigSource(str, enum.Enum):
    env = "env"
    cli = "cli"
    file = "file"


class ClientConfig(BaseModel):
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
    config_source: str = ConfigSource.cli
    config_file: str | None = None
    start_router: bool
    reload: bool

    open_timeout: int | None = None
    ping_interval: int | None = None
    ping_timeout: int | None = None

    authid: str | None = None
    ticket: str | None = None
    secret: str | None = None
    private_key: str | None = None
