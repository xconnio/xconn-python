from argparse import ArgumentParser
from dataclasses import dataclass
import importlib
import inspect
import os
import sys
from typing import get_type_hints

from pydantic import BaseModel
import yaml

from xconn.client import Client, AsyncClient
from xconn.async_session import AsyncSession
from xconn import App, run
from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result


@dataclass
class ClientConfig:
    entrypoint: str
    url: str
    realm: str
    authid: str
    auth_method: str


async def register_async(session: AsyncSession, uri: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"procedure '{uri}' must be a coroutine function")

    pydantic_model, response_model, return_type_is_result, positional_args, response_positional_args = (
        _validate_function(func, uri)
    )

    async def _handle_invocation(invocation: Invocation) -> Result:
        if pydantic_model is not None:
            args = invocation.args if invocation.args is not None else []
            kwargs = invocation.kwargs if invocation.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))

            result = await func(pydantic_model(**args_with_keys, **kwargs))
            return _handle_result(result, response_model, positional_args, response_positional_args)

        result = await func(invocation)
        return _handle_result(result, response_model, positional_args, response_positional_args)

    await session.register(uri, _handle_invocation)


def _validate_function(func: callable, uri: str):
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    hints = get_type_hints(func)
    return_type = hints.pop("return") if "return" in hints else None

    if Invocation in hints.values():
        if len(hints) != 1:
            raise RuntimeError(f"Cannot use other types than 'Invocation' as arguments in procedure '{uri}'")

    pydantic_model = None
    positional_args = []
    for type_ in hints.values():
        if issubclass(type_, BaseModel):
            if len(hints) != 1:
                raise RuntimeError(f"Cannot mix pydantic dataclass with other types in signature of procedure '{uri}'")

            pydantic_model = type_

            for key, value in pydantic_model.model_fields.items():
                if value.is_required:
                    positional_args.append(key)

    response_model = None
    response_positional_args = []
    return_type_is_result = return_type is Result
    if return_type_is_result:
        if func.__xconn_response_model__ is not None:
            response_model = func.__xconn_response_model__
            for key, value in response_model.model_fields.items():
                if value.is_required:
                    response_positional_args.append(key)

    return pydantic_model, response_model, return_type_is_result, positional_args, response_positional_args


def _handle_result(
    result: Result | None,
    response_model: type[BaseModel] | None,
    positional_args: list[str],
    response_positional_args: list[str],
):
    if result is None:
        if response_model is not None:
            raise ApplicationError("wamp.error.internal_error")

        return Result()

    if isinstance(result, Result) and response_model is not None:
        response_args = result.args if result.args is not None else []
        response_kwargs = result.kwargs if result.kwargs is not None else {}

        if len(response_args) != len(positional_args):
            raise ApplicationError("foo.bar.2")

        args_with_keys = dict(zip(response_positional_args, response_args))

        args = response_model(**args_with_keys, **response_kwargs)
        return Result(args=[args.dict()])

    if isinstance(result, list):
        raise ApplicationError("foo.bar.3")

    return Result(args=[result])


def subscribe(session, event: Event):
    pass


def handle_start(app: str, url: str, realm: str, directory: str):
    config_path = os.path.join(directory, "client.yaml")
    if not os.path.exists(config_path):
        print("client.yaml not found, initialize a client first")
        exit(1)

    with open(config_path) as f:
        config_raw = yaml.safe_load(f)

    config = ClientConfig(**config_raw)

    split = app.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    sys.path.append(directory)
    module = importlib.import_module(split[0])
    app: App = getattr(module, split[1])
    if not isinstance(app, App):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    async def _connect_async():
        client = AsyncClient()
        session = await client.connect(config.url, config.realm)
        app.set_session(session)

        for uri, func in app.procedures.items():
            await register_async(session, uri, func)

        for uri, func in app.topics.items():
            await session.subscribe(uri, func)

        print("connected", session.base_session.realm)

    def _connect_sync():
        client = Client()
        session = client.connect(config.url, config.realm)
        app.set_session(session)

        for uri, func in app.procedures.items():
            session.register(uri, func)

        for uri, func in app.topics.items():
            session.subscribe(uri, func)

        print("connected", session.base_session.realm)

    run(_connect_async())
    # _connect_sync()


def handle_init(url: str, realm: str, authid: str, auth_method: str):
    if os.path.exists("client.yaml"):
        print("client.yaml already exists")
        exit(1)

    with open("client.yaml", "w") as f:
        f.write(
            yaml.dump(
                {
                    "entrypoint": "main:app",
                    "url": url,
                    "realm": realm,
                    "authid": authid,
                    "auth_method": auth_method,
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
    start.add_argument("--url", type=str, default="ws://127.0.0.1:8080/ws")
    start.add_argument("--realm", type=str, default="realm1")
    start.add_argument("--directory", type=str, default=".")
    start.set_defaults(func=lambda args: handle_start(args.APP, args.url, args.realm, args.directory))

    stop = client_subparsers.add_parser("stop", help="Stop client")
    stop.add_argument("--directory", type=str, default=".")
    stop.set_defaults(func=lambda args: handle_stop(args.directory))

    init = client_subparsers.add_parser("init", help="Init client")
    init.add_argument("--url", type=str, default="ws://127.0.0.1:8080/ws")
    init.add_argument("--realm", type=str, default="realm1")
    init.add_argument("--authid", type=str, default="anonymous")
    init.add_argument("--authmethod", type=str, default="anonymous")
    init.set_defaults(func=lambda args: handle_init(args.url, args.realm, args.authid, args.authmethod))
