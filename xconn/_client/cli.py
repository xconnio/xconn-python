import os
import sys
import threading

from pydantic import ValidationError

from xconn._client import helpers
from xconn.types import WebsocketConfig
from xconn._client.helpers import connect
from xconn._client.watcher import start_file_watcher
from xconn._client.types import ClientConfig, CommandArgs, ConfigSource


def handle_start(command_args: CommandArgs):
    if command_args.config_source == ConfigSource.cli:
        try:
            config = ClientConfig(
                url=command_args.url,
                realm=command_args.realm,
                authid=command_args.authid,
                secret=command_args.secret,
                ticket=command_args.ticket,
                private_key=command_args.private_key,
            )
        except ValidationError as e:
            print("Invalid input:")
            for error in e.errors():
                loc = " -> ".join(map(str, error["loc"]))
                msg = error["msg"]
                print(f" - {loc}: {msg}")

            exit(1)

        config.websocket_config = WebsocketConfig(
            command_args.open_timeout, command_args.ping_interval, command_args.ping_timeout
        )
    elif command_args.config_source == ConfigSource.env:
        config = helpers.load_config_from_env(command_args)
        # Now override config if something was provided explicitly from command line
        config = helpers.update_config_from_cli(config, command_args)
    elif command_args.config_source == ConfigSource.file:
        config = helpers.load_config_from_file(command_args)
        # Now override config if something was provided explicitly from command line
        config = helpers.update_config_from_cli(config, command_args)
    else:
        raise RuntimeError(f"Unknown config_source: {command_args.config_source}")

    helpers.validate_auth_inputs(config)
    config.authmethod = helpers.select_authmethod(config)

    if command_args.reload:

        def restart():
            # Restart process due to file changes
            os.execv(sys.executable, [sys.executable] + sys.argv)

        threading.Thread(target=start_file_watcher, args=(restart,), daemon=True).start()

    connect(command_args.app, config, start_router=command_args.start_router, directory=command_args.directory)
