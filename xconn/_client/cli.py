from argparse import ArgumentParser
import importlib
import os
import sys
import ipaddress

import yaml

from xconn import App, run
from xconn._client.sync import connect_sync
from xconn._client.async_ import connect_async
from xconn._client.types import ClientConfig


def handle_start(
    app: str,
    url: str,
    realm: str,
    directory: str,
    asyncio: bool,
    schema_host: str,
    schema_port: int,
    start_router: bool = False,
):
    config_path = os.path.join(directory, "client.yaml")
    if not os.path.exists(config_path):
        print("client.yaml not found, initialize a client first")
        exit(1)

    # validate schema host
    ipaddress.ip_address(schema_host)

    with open(config_path) as f:
        config_raw = yaml.safe_load(f)

    config = ClientConfig(**config_raw)

    if url is not None and url != "":
        config.url = url

    if realm is not None and realm != "":
        config.realm = realm

    if schema_host is not None and schema_host != "":
        config.schema_host = schema_host

    if schema_port is not None and schema_port != "":
        config.schema_port = schema_port

    split = app.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    sys.path.append(directory)
    module = importlib.import_module(split[0])
    app: App = getattr(module, split[1])
    if not isinstance(app, App):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    if asyncio:
        run(connect_async(app, config, serve_schema=True, start_router=start_router))
    else:
        connect_sync(app, config, serve_schema=True, start_router=start_router)


def handle_init(url: str, realm: str, authid: str, authmethod: str, secret: str, schema_host: str, schema_port: int):
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
                    "schema_host": schema_host,
                    "schema_port": schema_port,
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
    start.add_argument("--schema-host", type=str, default="127.0.0.1")
    start.add_argument("--schema-port", type=int, default=9000)
    start.add_argument("--router", action="store_true", default=False)
    start.set_defaults(
        func=lambda args: handle_start(
            args.APP,
            args.url,
            args.realm,
            args.directory,
            args.asyncio,
            args.schema_host,
            args.schema_port,
            args.router,
        )
    )

    stop = client_subparsers.add_parser("stop", help="Stop client")
    stop.add_argument("--directory", type=str, default=".")
    stop.set_defaults(func=lambda args: handle_stop(args.directory))

    init = client_subparsers.add_parser("init", help="Init client")
    init.add_argument("--url", type=str, default="ws://127.0.0.1:8080/ws")
    init.add_argument("--realm", type=str, default="realm1")
    init.add_argument("--authid", type=str, default="anonymous")
    init.add_argument("--authmethod", type=str, default="anonymous")
    init.add_argument("--secret", type=str, default="")
    init.add_argument("--schema-host", type=str, default="127.0.0.1")
    init.add_argument("--schema-port", type=int, default=9000)
    init.set_defaults(
        func=lambda args: handle_init(
            args.url, args.realm, args.authid, args.authmethod, args.secret, args.schema_host, args.schema_port
        )
    )
