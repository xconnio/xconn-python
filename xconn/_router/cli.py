import os
import shutil
import signal
import threading
from pathlib import Path
from argparse import ArgumentParser

import yaml

from xconn import Server, Router
from xconn._router import helpers
from xconn._router.types import RouterConfig
from xconn._router.authenticator import ServerAuthenticator

DIRECTORY_CONFIG = ".xconn"
CONFIG_FILE = os.path.join(DIRECTORY_CONFIG, "config.yaml")


def start(args):
    if not os.path.exists(CONFIG_FILE):
        print("config.yaml not found")
        exit(1)

    with open(CONFIG_FILE) as f:
        data = yaml.safe_load(f)

    config: RouterConfig = helpers.validate_config(data)

    router = Router()

    for realm in config.realms:
        router.add_realm(realm.name)

    authenticator = ServerAuthenticator(config.authenticators)

    stop_event = threading.Event()

    def handle_signal(signum, frame):
        print(f"\nReceived signal {signal.Signals(signum).name}, stopping...")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, handle_signal)

    for transport in config.transports:
        server = Server(router, authenticator)
        threading.Thread(target=helpers.start_server_sync, args=(server, transport), daemon=True).start()

    stop_event.wait()


def stop(args):
    print("Router stopped")


def init(args):
    if os.path.exists(CONFIG_FILE):
        print("config.yaml already exists")
        exit(1)

    os.makedirs(DIRECTORY_CONFIG, exist_ok=True)
    base_dir = Path(__file__).parent
    source_path = os.path.join(base_dir, "config.yaml.in")
    shutil.copy(source_path, CONFIG_FILE)


def add_router_subparser(subparsers):
    router_parser: ArgumentParser = subparsers.add_parser("router", help="Router operations")
    router_subparsers = router_parser.add_subparsers(dest="router_command")

    router_parser.set_defaults(print_help=router_parser.print_help)

    router_subparsers.add_parser("start", help="Start router").set_defaults(func=start)
    router_subparsers.add_parser("stop", help="Stop router").set_defaults(func=stop)
    router_subparsers.add_parser("init", help="Init router").set_defaults(func=init)
