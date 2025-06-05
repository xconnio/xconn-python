import time
import socket
import asyncio
import inspect
import json
from typing import get_type_hints
from urllib.parse import urlparse

from aiohttp import web
from pydantic import BaseModel
from wampproto.auth import (
    WAMPCRAAuthenticator,
    TicketAuthenticator,
    CryptoSignAuthenticator,
    AnonymousAuthenticator,
    IClientAuthenticator,
)

from xconn import Router, Server
from xconn._client.types import ClientConfig
from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result


def is_primitive(obj) -> bool:
    return isinstance(obj, (str, int, float, bool, bytes, type(None)))


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

    response_model = getattr(func, "__xconn_response_model__", None)
    response_positional_args = []
    if response_model is not None:
        for key, value in response_model.model_fields.items():
            if value.is_required:
                response_positional_args.append(key)

    return pydantic_model, response_model, positional_args, response_positional_args


def _handle_result(
    result: Result | tuple | None,
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
                f"Procedure returned a single primitive but response model has "
                f"{len(response_positional_args)} positional args.",
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
                f"Procedure returned {len(result)} values but the response model has "
                f"{len(response_positional_args)} args.",
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


def _sanitize_incoming_data(args: list, kwargs: dict, model_positional_args: list[str]):
    args = args if args is not None else []
    kwargs = kwargs if kwargs is not None else {}

    args_with_keys = dict(zip(model_positional_args, args))
    args_with_keys.update(kwargs)

    return args_with_keys


def collect_docs(uri: str, func: callable, type_: str):
    model, response_model, positional_args, response_positional_args = _validate_procedure_function(func, uri)

    data = {"uri": uri, "type": type_}
    if model is not None:
        data["in_model"] = model.model_json_schema()

    if response_model is not None:
        data["out_model"] = response_model.model_json_schema()

    return data


def create_app(docs: list[dict], endpoint: str):
    app = web.Application()

    async def serve_schema(_):
        return web.json_response(docs)

    app.router.add_get(endpoint, serve_schema)
    return app


async def serve_schema_async(host: str, port: int, docs: list, endpoint="/schema.json"):
    app = create_app(docs, endpoint)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Schema available at http://{host}:{port}{endpoint}")


def serve_schema_sync(host: str, port: int, docs, endpoint="/schema.json"):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(serve_schema_async(host, port, docs, endpoint=endpoint))
    loop.run_forever()


def select_authenticator(config: ClientConfig) -> IClientAuthenticator:
    if config.authmethod == "cryptosign" or config.authmethod == "wampcra" or config.authmethod == "ticket":
        if config.secret == "":
            raise RuntimeError("secret must not be empty")

        if config.authmethod == "wampcra":
            auth = WAMPCRAAuthenticator(config.authid, config.secret)
        elif config.authmethod == "ticket":
            auth = TicketAuthenticator(config.authid, config.ticket)
        else:
            auth = CryptoSignAuthenticator(config.authid, config.private_key)
    else:
        auth = AnonymousAuthenticator(authid=config.authid)

    return auth


async def start_server_async(config: ClientConfig):
    r = Router()
    r.add_realm(config.realm)
    server = Server(r)
    url_parsed = urlparse(config.url)
    await server.start(url_parsed.hostname, url_parsed.port)


def start_server_sync(config: ClientConfig):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_server_async(config))
    loop.run_forever()


def is_non_empty(value):
    return value is not None and value != ""


def validate_auth_inputs(private_key: str | None, ticket: str | None, secret: str | None) -> None:
    if is_non_empty(private_key) and is_non_empty(ticket):
        raise ValueError("provide only one of private key, ticket or secret")
    elif is_non_empty(ticket) and is_non_empty(secret):
        raise ValueError("provide only one of private key, ticket or secret")
    elif is_non_empty(private_key) and is_non_empty(secret):
        raise ValueError("provide only one of private key, ticket or secret")


def select_authmethod(config: ClientConfig) -> str:
    if is_non_empty(config.private_key) and not config.ticket and not config.secret:
        return CryptoSignAuthenticator.TYPE
    elif is_non_empty(config.ticket) and not config.private_key and not config.secret:
        return TicketAuthenticator.TYPE
    elif is_non_empty(config.secret) and not config.private_key and not config.ticket:
        return WAMPCRAAuthenticator.TYPE

    return AnonymousAuthenticator.TYPE


def wait_for_server(host: str, port: int, timeout: float):
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            try:
                sock.connect((host, port))
                return True
            except (ConnectionRefusedError, socket.timeout):
                time.sleep(0.2)
    raise TimeoutError(f"Server did not start listening on {host}:{port} within {timeout} seconds.")
