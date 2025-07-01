import os

from xconn._client import helpers
from xconn.types import WebsocketConfig
from xconn._client.helpers import connect
from xconn._client.types import ClientConfig, CommandArgs, ConfigSource


def handle_start(command_args: CommandArgs):
    if command_args.config_source == ConfigSource.cli:
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
    elif command_args.config_source == ConfigSource.env:
        config = helpers.load_config_from_env(command_args.config_file)
    elif command_args.config_source == ConfigSource.file:
        config = helpers.load_config_from_file(command_args.config_file)
    else:
        config_path = os.path.join(command_args.directory, "xcorn.yaml")
        if not os.path.exists(config_path):
            print("xcorn.yaml not found, initialize a client first")
            exit(1)

        config = helpers.load_config_from_yaml(config_path)

    config = helpers.update_config_from_cli(config, command_args)

    helpers.validate_auth_inputs(config)
    config.authmethod = helpers.select_authmethod(config)
    connect(command_args.app, config, start_router=command_args.start_router, directory=command_args.directory)
