from argparse import ArgumentParser
from dataclasses import dataclass
import importlib
import inspect
import json
import os
import sys
from typing import get_type_hints, Union

from pydantic import BaseModel
import yaml

from xconn.client import Client, AsyncClient
from xconn.async_session import AsyncSession
from xconn.session import Session
from xconn import App, run
from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result


Primitive = Union[str, int, float, bool, None, bytes, dict, tuple]


@dataclass
class ClientConfig:
    url: str
    realm: str
    authid: str
    authmethod: str
    directory: str


async def register_async(session: AsyncSession, uri: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must be a coroutine")

    model, response_model, positional_args, response_positional_args = _validate_procedure_function(func, uri)

    async def _handle_invocation(invocation: Invocation) -> Result:
        if model is not None:
            args = invocation.args if invocation.args is not None else []
            kwargs = invocation.kwargs if invocation.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))

            result = await func(model(**args_with_keys, **kwargs))
            return _handle_result(result, response_model, response_positional_args)

        result = await func(invocation)
        return _handle_result(result, response_model, response_positional_args)

    await session.register(uri, _handle_invocation)


def register_sync(session: Session, uri: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must not be a coroutine")

    model, response_model, positional_args, response_positional_args = _validate_procedure_function(func, uri)

    def _handle_invocation(invocation: Invocation) -> Result:
        if model is not None:
            args = invocation.args if invocation.args is not None else []
            kwargs = invocation.kwargs if invocation.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))

            result = func(model(**args_with_keys, **kwargs))
            return _handle_result(result, response_model, response_positional_args)

        result = func(invocation)
        return _handle_result(result, response_model, response_positional_args)

    session.register(uri, _handle_invocation)


def _validate_procedure_function(func: callable, uri: str):
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    hints = get_type_hints(func)
    hints.pop("return") if "return" in hints else None

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

    response_model = func.__xconn_response_model__
    response_positional_args = []
    if response_model is not None:
        for key, value in response_model.model_fields.items():
            if value.is_required:
                response_positional_args.append(key)

    return pydantic_model, response_model, positional_args, response_positional_args


def is_primitive(obj) -> bool:
    return isinstance(obj, (str, int, float, bool, bytes, type(None)))


def _handle_result(
    result: Result | tuple | Primitive,
    response_model: type[BaseModel] | None,
    response_positional_args: list[str],
) -> Result:
    if result is None:
        if response_model is not None:
            raise ApplicationError(
                "wamp.error.internal_error", "Procedure returned None, but a response model was provided."
            )

        return Result()

    if isinstance(result, Result):
        if response_model is None:
            return result

        response_args = result.args if result.args is not None else []
        response_kwargs = result.kwargs if result.kwargs is not None else {}

        # If the Result object was returned, we need to be able to map
        # its args to their keys so that the pydantic model can be initialized.
        if len(response_args) != len(response_positional_args):
            raise ApplicationError("wamp.error.internal_error")

        args_with_keys = dict(zip(response_positional_args, response_args))

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**args_with_keys, **response_kwargs)
        return Result(args=[args.model_dump()])

    if response_model is None:
        # No response model provided, return the result as-is.
        # We avoid validating the data and shift the responsibility
        # to the serializer.
        return Result(args=[result])

    if is_primitive(result):
        if len(response_positional_args) != 1:
            raise ApplicationError(
                "wamp.error.internal_error",
                f"Procedure returned a single primitive but response model has {len(response_positional_args)} positional args.",
            )

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**{response_positional_args[0]: result})
        return Result(args=[args.model_dump()])

    # If the result is a tuple, it usually means a python function returned multiple values.
    # Though that might not always be the case, and a function may explicitly return a tuple as well.
    if isinstance(result, tuple):
        if len(result) != len(response_positional_args):
            raise ApplicationError(
                "wamp.error.internal_error",
                f"Procedure returned {len(result)} values but the response model has {len(response_positional_args)} args.",
            )

        args_with_keys = dict(zip(response_positional_args, result))

        # FIXME: catch ValidationError and return ApplicationError
        args = response_model(**args_with_keys)
        return Result(args=[args.model_dump()])

    if isinstance(result, list):
        # FIXME: catch ValidationError and return ApplicationError
        return Result(args=[json.loads(response_model.from_orm(item).json()) for item in result])

    # FIXME: catch ValidationError and return ApplicationError
    return Result(args=[json.loads(response_model.from_orm(result).json())])


async def subscribe_async(session: AsyncSession, topic: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    async def _handle_event(event: Event):
        if model is not None:
            args = event.args if event.args is not None else []
            kwargs = event.kwargs if event.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))

            await func(model(**args_with_keys, **kwargs))

        await func(event)

    await session.subscribe(topic, _handle_event)


def subscribe_sync(session: Session, topic: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must not be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    def _handle_event(event: Event):
        if model is not None:
            args = event.args if event.args is not None else []
            kwargs = event.kwargs if event.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))
            func(model(**args_with_keys, **kwargs))

        func(event)

    session.subscribe(topic, _handle_event)


def _validate_topic_function(func: callable, uri: str):
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    hints = get_type_hints(func)
    hints.pop("return") if "return" in hints else None

    if Event in hints.values():
        if len(hints) != 1:
            raise RuntimeError(f"Cannot use other types than 'Event' as arguments in subscription '{uri}'")

    pydantic_model = None
    positional_args = []
    for type_ in hints.values():
        if issubclass(type_, BaseModel):
            if len(hints) != 1:
                raise RuntimeError(
                    f"Cannot mix pydantic dataclass with other types in signature of subscription '{uri}'"
                )

            pydantic_model = type_

            for key, value in pydantic_model.model_fields.items():
                if value.is_required:
                    positional_args.append(key)

    return pydantic_model, positional_args


def handle_start(app: str, url: str, realm: str, directory: str, asyncio: bool):
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

    if asyncio:
        run(connect_async(app, config))
    else:
        connect_sync(app, config)


async def connect_async(app: App, config: ClientConfig):
    client = AsyncClient()
    session = await client.connect(config.url, config.realm)
    app.set_session(session)

    for uri, func in app.procedures.items():
        await register_async(session, uri, func)

    for uri, func in app.topics.items():
        await subscribe_async(session, uri, func)

    print("connected", session.base_session.realm)


def connect_sync(app: App, config: ClientConfig):
    client = Client()
    session = client.connect(config.url, config.realm)
    app.set_session(session)

    for uri, func in app.procedures.items():
        register_sync(session, uri, func)

    for uri, func in app.topics.items():
        subscribe_sync(session, uri, func)

    print("connected", session.base_session.realm)


def handle_init(url: str, realm: str, authid: str, authmethod: str, directory: str):
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
                    "directory": directory,
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
    start.add_argument("--asyncio", action="store_true", default=False)
    start.set_defaults(func=lambda args: handle_start(args.APP, args.url, args.realm, args.directory, args.asyncio))

    stop = client_subparsers.add_parser("stop", help="Stop client")
    stop.add_argument("--directory", type=str, default=".")
    stop.set_defaults(func=lambda args: handle_stop(args.directory))

    init = client_subparsers.add_parser("init", help="Init client")
    init.add_argument("--url", type=str, default="ws://127.0.0.1:8080/ws")
    init.add_argument("--realm", type=str, default="realm1")
    init.add_argument("--authid", type=str, default="anonymous")
    init.add_argument("--authmethod", type=str, default="anonymous")
    init.add_argument("--directory", type=str, default=".")
    init.set_defaults(func=lambda args: handle_init(args.url, args.realm, args.authid, args.authmethod, args.directory))
