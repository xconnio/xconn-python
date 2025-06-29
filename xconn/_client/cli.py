import os

import yaml

from xconn._client import helpers
from xconn.types import WebsocketConfig
from xconn._client.sync import connect_sync
from xconn._client.async_ import connect_async
from xconn._client.types import ClientConfig, CommandArgs


def handle_start(command_args: CommandArgs):
    if command_args.no_config:
        helpers.validate_auth_inputs(command_args.private_key, command_args.ticket, command_args.secret)
        config = ClientConfig(
            url=command_args.url,
            realm=command_args.realm,
            authid=command_args.authid,
            secret=command_args.secret,
            ticket=command_args.ticket,
            private_key=command_args.private_key,
        )
        config.websocket_config = WebsocketConfig(
            command_args.open_timeout, command_args.ping_interval, command_args.ping_timeout
        )

    else:
        config_path = os.path.join(command_args.directory, "xcorn.yaml")
        if not os.path.exists(config_path):
            print("xcorn.yaml not found, initialize a client first")
            exit(1)

        flags = (
            command_args.url,
            command_args.realm,
            command_args.authid,
            command_args.secret,
            command_args.ticket,
        )
        if any(flag is not None for flag in flags):
            raise RuntimeError("Use either config file OR the individual flags, not both")

        with open(config_path) as f:
            config_raw = yaml.safe_load(f)

        config = ClientConfig(**config_raw)
        helpers.validate_auth_inputs(command_args.private_key, command_args.ticket, command_args.secret)

    config.authmethod = helpers.select_authmethod(config)

    if command_args.asyncio:
        connect_async(
            command_args.app, config, start_router=command_args.start_router, directory=command_args.directory
        )
    else:
        connect_sync(command_args.app, config, start_router=command_args.start_router, directory=command_args.directory)
