import importlib
import os
import sys

import yaml

from xconn import App, run
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
        config_path = os.path.join(command_args.directory, "xapp.yaml")
        if not os.path.exists(config_path):
            print("xapp.yaml not found, initialize a client first")
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
    if os.path.exists("xapp.yaml"):
        print("xapp.yaml already exists")
        exit(1)

    if os.path.exists("xapp.py"):
        print("xapp.py already exists")
        exit(1)

    with open("xapp.yaml", "w") as f:
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

    with open("sample.py", "w") as f:
        f.write("""from xconn import App

app = App()

@app.register("io.xconn.hello")
async def my_procedure(first_name: str, last_name: str, age: int):
    print(first_name + " " + last_name + " " + str(age))
    return first_name, last_name, age


@app.subscribe("io.xconn.publish")
async def my_topic():
    print("received event...")
""")

    print("XConn App initialized.")
    print("The config is xapp.yaml and sample app is sample.py. Run below command to start the sample")
    print("")
    print("xapp start sample:app --asyncio --start-router")


def handle_stop(directory: str):
    # TODO: when the app starts create a xapp.pid with the pid of the process
    #  when stop is called just request the OS to kill that PID.
    print(directory)


def add_client_subparser(subparsers):
    start = subparsers.add_parser("start", help="Start XConn App")
    start.add_argument("APP", type=str)
    start.add_argument("--url", type=str)
    start.add_argument("--realm", type=str)
    start.add_argument("--directory", type=str, default=".")
    start.add_argument("--asyncio", action="store_true", default=False)
    start.add_argument("--start-router", action="store_true", default=False)
    start.add_argument("--authid", type=str)
    start.add_argument("--secret", type=str)
    start.add_argument("--ticket", type=str)
    start.add_argument("--private-key", type=str)
    start.add_argument("--no-config", action="store_true", default=False)
    start.add_argument("--open-timeout", type=int, default=10)
    start.add_argument("--ping-interval", type=int, default=20)
    start.add_argument("--ping-timeout", type=int, default=20)
    start.set_defaults(func=lambda args: handle_start(CommandArgs(**vars(args))))

    stop = subparsers.add_parser("stop", help="Stop a running XConn App")
    stop.add_argument("--directory", type=str, default=".")
    stop.set_defaults(func=lambda args: handle_stop(args.directory))

    init = subparsers.add_parser("init", help="Init a new XConn App")
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
