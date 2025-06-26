import argparse

from xconn._client.cli import add_client_subparser


def main():
    parser = argparse.ArgumentParser(description="XConn CLI")
    subparsers = parser.add_subparsers(dest="component")

    # Add subcommands from other modules
    add_client_subparser(subparsers)

    args = parser.parse_args()

    if hasattr(args, "func"):
        args.func(args)
    elif hasattr(args, "print_help"):
        args.print_help()
    else:
        parser.print_help()
