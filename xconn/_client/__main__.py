import argparse

from xconn._client.cli import handle_start, CommandArgs
from xconn._client.types import ConfigSource


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("APP", type=str)
    parser.add_argument("--url", type=str)
    parser.add_argument("--realm", type=str)
    parser.add_argument("--authid", type=str)
    parser.add_argument("--secret", type=str)
    parser.add_argument("--ticket", type=str)
    parser.add_argument("--private-key", type=str)

    # transport options
    parser.add_argument("--open-timeout", type=int, default=10)
    parser.add_argument("--ping-interval", type=int, default=20)
    parser.add_argument("--ping-timeout", type=int, default=20)

    # misc
    parser.add_argument("--directory", type=str, default=".")
    parser.add_argument("--start-router", action="store_true", default=False)
    parser.add_argument("--reload", action="store_true", default=False)
    parser.add_argument(
        "--config-source", type=str, choices=[e.value for e in ConfigSource], default=ConfigSource.cli.value
    )
    parser.add_argument("--config-file", type=str)
    args = parser.parse_args()

    handle_start(CommandArgs(**vars(args)))
