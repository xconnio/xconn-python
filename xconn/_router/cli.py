from argparse import ArgumentParser


def start(args):
    print("Router started")


def stop(args):
    print("Router stopped")


def init(args):
    print("Router initialized")


def add_router_subparser(subparsers):
    router_parser: ArgumentParser = subparsers.add_parser("router", help="Router operations")
    router_subparsers = router_parser.add_subparsers(dest="router_command")

    router_parser.set_defaults(print_help=router_parser.print_help)

    router_subparsers.add_parser("start", help="Start router").set_defaults(func=start)
    router_subparsers.add_parser("stop", help="Stop router").set_defaults(func=stop)
    router_subparsers.add_parser("init", help="Init router").set_defaults(func=init)
