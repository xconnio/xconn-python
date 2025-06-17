import importlib
import os
import sys
from argparse import ArgumentParser, Action

import yaml

from xconn import App, run
from xconn._client import helpers
from xconn.types import WebsocketConfig
from xconn._client.sync import connect_sync
from xconn._client.async_ import connect_async
from xconn._client.types import ClientConfig, CommandArgs


class FromConfigAction(Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is None:
            setattr(namespace, self.dest, True)
        else:
            setattr(namespace, self.dest, values)


def handle_start(command_args: CommandArgs):
    if command_args.from_config:
        if isinstance(command_args.from_config, bool):
            config_path = os.path.join(command_args.directory, "client.yaml")
        else:
            config_path = os.path.join(command_args.directory, command_args.from_config)
        if not os.path.exists(config_path):
            print(f"config file '{config_path}' not found, initialize a client first")
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
    else:
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

    config.authmethod = helpers.select_authmethod(config)

    split = command_args.app.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    sys.path.append(command_args.directory)
    module = importlib.import_module(split[0])
    app: App = getattr(module, split[1])
    if not isinstance(app, App):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    if command_args.asyncio:
        run(connect_async(app, config, start_router=command_args.start_router))
    else:
        connect_sync(app, config, start_router=command_args.start_router)


def handle_init(
    url: str,
    realm: str,
    authid: str,
    authmethod: str,
    secret: str,
    open_timeout: int,
    ping_interval: int,
    ping_timeout: int,
):
    if os.path.exists("client.yaml"):
        print("client.yaml already exists")
        exit(1)

    with open("client.yaml", "w") as f:
        f.write(
            yaml.dump(
                {
                    "url": url,
                    "realm": realm,
                    "authid": authid,
                    "authmethod": authmethod,
                    "secret": secret,
                    "websocket_config": {
                        "open_timeout": open_timeout,
                        "ping_interval": ping_interval,
                        "ping_timeout": ping_timeout,
                    },
                }
            )
        )


def handle_stop(directory: str):
    print(directory)


def add_client_subparser(subparsers):
    client_parser: ArgumentParser = subparsers.add_parser("client", help="Client operations")
    client_subparsers = client_parser.add_subparsers(dest="client_command")

    client_parser.set_defaults(print_help=client_parser.print_help)

    start = client_subparsers.add_parser("start", help="Start client")
    start.add_argument("APP", type=str)
    start.add_argument("--url", type=str)
    start.add_argument("--realm", type=str)
    start.add_argument("--directory", type=str, default=".")
    start.add_argument("--asyncio", action="store_true", default=False)
    start.add_argument("--router", action="store_true", default=False)
    start.add_argument("--authid", type=str)
    start.add_argument("--secret", type=str)
    start.add_argument("--ticket", type=str)
    start.add_argument("--private-key", type=str)
    start.add_argument("--open-timeout", type=int, default=10)
    start.add_argument("--ping-interval", type=int, default=20)
    start.add_argument("--ping-timeout", type=int, default=20)
    start.add_argument("--schema-proc", type=str)
    start.add_argument("--from-config", nargs="?", action=FromConfigAction, default=None)
    start.set_defaults(func=lambda args: handle_start(CommandArgs(**vars(args))))

    stop = client_subparsers.add_parser("stop", help="Stop client")
    stop.add_argument("--directory", type=str, default=".")
    stop.set_defaults(func=lambda args: handle_stop(args.directory))

    init = client_subparsers.add_parser("init", help="Init client")
    init.add_argument("--url", type=str, default="ws://127.0.0.1:8080/ws")
    init.add_argument("--realm", type=str, default="realm1")
    init.add_argument("--authid", type=str, default="anonymous")
    init.add_argument("--authmethod", type=str, default="anonymous")
    init.add_argument("--secret", type=str, default="")
    init.add_argument("--open-timeout", type=int, default=10)
    init.add_argument("--ping-interval", type=int, default=20)
    init.add_argument("--ping-timeout", type=int, default=20)
    init.set_defaults(
        func=lambda args: handle_init(
            args.url,
            args.realm,
            args.authid,
            args.authmethod,
            args.secret,
            args.open_timeout,
            args.ping_interval,
            args.ping_timeout,
        )
    )
