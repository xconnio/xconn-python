import contextlib
import os
import time
import socket
import asyncio
from dataclasses import dataclass
import inspect
import json
import importlib
import sys
from typing import (
    get_type_hints,
    Type,
    Optional,
    Any,
    Callable,
    ContextManager,
    AsyncContextManager,
    Awaitable,
    get_origin,
    Union,
    get_args,
)
from urllib.parse import urlparse

import yaml
from aiohttp import web
from dotenv import load_dotenv
from pydantic import BaseModel, create_model, ValidationError
from wampproto.auth import (
    WAMPCRAAuthenticator,
    TicketAuthenticator,
    CryptoSignAuthenticator,
    AnonymousAuthenticator,
    IClientAuthenticator,
)

from xconn import Router, Server
from xconn.app import App, ExecutionMode
from xconn._client.types import ClientConfig, CommandArgs
from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result, Depends, CallDetails, RegisterOptions, SubscribeOptions, EventDetails

MAX_WAIT = 60
INITIAL_WAIT = 1


@dataclass
class BaseMetadata:
    request_model: Type[BaseModel] | None
    request_args: list[str]
    request_kwargs: list[str]

    no_args: bool
    dynamic_model: bool

    dependencies: dict[str, Callable]
    ctx_dependencies: dict[str, ContextManager]
    async_dependencies: dict[str, Awaitable]
    async_ctx_dependencies: dict[str, AsyncContextManager]

    details_field: str | None
    positional_field_name: str | None

    uri: str


@dataclass
class ProcedureMetadata(BaseMetadata):
    response_model: Type[BaseModel] | None
    response_args: list[str]
    response_kwargs: list[str]

    allowed_roles: list[str]

    register_options: dict[str, Any] | RegisterOptions | None
    func: callable


@dataclass
class EventMetadata(BaseMetadata):
    subscribe_options: dict[str, Any] | SubscribeOptions | None
    func: callable


def create_model_from_func(func):
    signature = inspect.signature(func)
    type_hints = get_type_hints(func)
    fields = {}

    for param_name, param in signature.parameters.items():
        annotated_type = type_hints.get(param_name)
        if (
            is_subclass_of_any(annotated_type, CallDetails)
            or is_subclass_of_any(annotated_type, Depends)
            or is_subclass_of_any(annotated_type, EventDetails)
        ):
            continue

        # Handle default values
        if param.default is inspect.Parameter.empty:
            fields[param_name] = (annotated_type, ...)
        else:
            fields[param_name] = (Optional[annotated_type], param.default)

    return create_model(func.__name__.capitalize() + "Model", **fields)


def is_primitive(obj) -> bool:
    return isinstance(obj, (str, int, float, bool, bytes, type(None)))


def is_subclass_of_any(type_, base_class: Any) -> bool:
    origin = get_origin(type_)
    if origin is Union:
        return any(isinstance(arg, type) and issubclass(arg, base_class) for arg in get_args(type_))

    return isinstance(type_, type) and issubclass(type_, base_class)


def _assemble_base_metadata(
    func: callable,
    uri: str,
    incoming_class: type(Invocation) | type(Event),
    details_class: type(CallDetails) | type(EventDetails),
) -> BaseMetadata:
    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        if param.annotation is inspect._empty:
            raise RuntimeError(f"Missing type hint for parameter: '{name}' in function '{func.__name__}'")

    if issubclass(incoming_class, Event):
        context = "topic"
    elif issubclass(incoming_class, Invocation):
        context = "procedure"
    else:
        raise RuntimeError(f"incoming_class can be with Invocation or Event got='{incoming_class.__name__}'")

    if not issubclass(details_class, CallDetails) and not issubclass(details_class, EventDetails):
        raise RuntimeError(f"details_class can be either CallDetails or EventDetails got='{details_class.__name__}'")

    hints = get_type_hints(func)
    hints.pop("return", None)

    request_model = None
    request_args = []
    request_kwargs = []
    no_args = False
    dynamic_model = False

    dependencies = {}
    ctx_dependencies = {}
    async_dependencies = {}
    async_ctx_dependencies = {}
    for name, param in sig.parameters.items():
        if isinstance(param.default, Depends):
            sig = inspect.signature(param.default.dependency)

            if len(sig.parameters) != 0:
                raise RuntimeError("Dependency functions support no parameters")

            dep: Depends = param.default

            if dep.is_async:
                async_dependencies[name] = param.default.dependency
            elif dep.is_async_gen:
                async_ctx_dependencies[name] = param.default.dependency
            elif inspect.isgeneratorfunction(param.default.dependency):
                ctx_dependencies[name] = contextlib.contextmanager(param.default.dependency)
            elif inspect.isfunction(param.default.dependency) or inspect.ismethod(param.default.dependency):
                dependencies[name] = param.default.dependency

    for key in dependencies.keys():
        del hints[key]

    for key in ctx_dependencies.keys():
        del hints[key]

    for key in async_dependencies.keys():
        del hints[key]

    for key in async_ctx_dependencies.keys():
        del hints[key]

    # check if CallDetails are in the function
    details_field = None
    for name, type_ in hints.items():
        if is_subclass_of_any(type_, details_class):
            if details_field is not None:
                raise RuntimeError(f"Duplicate {details_class.__name__} in function '{func.__name__}'")

            details_field = name

    if details_field is not None:
        del hints[details_field]

    positional_field_name: str | None = None

    has_incoming_class_in_sig = False
    for name, type_ in hints.items():
        if issubclass(type_, BaseModel):
            if len(hints) != 1:
                raise RuntimeError(f"Cannot mix pydantic BaseModel with other types in signature of {context} '{uri}'")

            request_model = type_
            positional_field_name = name
            break

        if is_subclass_of_any(type_, incoming_class):
            if has_incoming_class_in_sig:
                raise RuntimeError(
                    f"Cannot use other types than '{incoming_class.__name__}' as arguments in {context} '{uri}'"
                )

            has_incoming_class_in_sig = True
            positional_field_name = name

    if Invocation in hints.values():
        if len(hints) != 1:
            raise RuntimeError(
                f"Cannot use other types than '{incoming_class.__name__}' as arguments in {context} '{uri}'"
            )
    elif request_model is not None:
        for key, value in request_model.model_fields.items():
            if value.is_required:
                request_args.append(key)
            else:
                request_kwargs.append(key)
    elif len(hints) == 0:
        no_args = True
    else:
        # let's create a dynamic pydantic model based on the procedure signature
        request_model = create_model_from_func(func)
        for key, value in request_model.model_fields.items():
            if value.is_required:
                request_args.append(key)
            else:
                request_kwargs.append(key)

        dynamic_model = True

    return BaseMetadata(
        request_model=request_model,
        request_args=request_args,
        request_kwargs=request_kwargs,
        no_args=no_args,
        dynamic_model=dynamic_model,
        dependencies=dependencies,
        ctx_dependencies=ctx_dependencies,
        async_dependencies=async_dependencies,
        async_ctx_dependencies=async_ctx_dependencies,
        details_field=details_field,
        positional_field_name=positional_field_name,
        uri=uri,
    )


def _validate_procedure_function(func: callable, uri: str) -> ProcedureMetadata:
    meta = _assemble_base_metadata(func, uri, Invocation, CallDetails)

    response_model = getattr(func, "__xconn_response_model__", None)
    response_args = []
    response_kwargs = []
    if response_model is not None:
        for key, value in response_model.model_fields.items():
            if value.is_required:
                response_args.append(key)
            else:
                response_kwargs.append(key)

    allowed_roles = getattr(func, "__xconn_allowed_roles__", [])
    register_options = getattr(func, "__xconn_register_options__", None)

    return ProcedureMetadata(
        request_model=meta.request_model,
        response_model=response_model,
        request_args=meta.request_args,
        response_args=response_args,
        request_kwargs=meta.request_kwargs,
        response_kwargs=response_kwargs,
        no_args=meta.no_args,
        dynamic_model=meta.dynamic_model,
        allowed_roles=allowed_roles,
        dependencies=meta.dependencies,
        ctx_dependencies=meta.ctx_dependencies,
        async_dependencies=meta.async_dependencies,
        async_ctx_dependencies=meta.async_ctx_dependencies,
        details_field=meta.details_field,
        positional_field_name=meta.positional_field_name,
        register_options=register_options,
        uri=meta.uri,
        func=func,
    )


def validate_invocation_parameters(invocation: Invocation, meta: ProcedureMetadata):
    msg = ""
    if invocation.args is not None and len(invocation.args) > len(meta.request_args):
        msg += "expected {} arguments, got {}".format(len(meta.request_args), len(invocation.args))

    if invocation.kwargs is not None and len(invocation.kwargs) > len(meta.request_kwargs):
        if msg != "":
            msg += ", "

        msg += "expected {} keyword arguments, got {}".format(len(meta.request_kwargs), len(invocation.kwargs))

    if msg != "":
        raise ApplicationError("wamp.error.invalid_arguments", msg)


def validate_event_parameters(event: Event, meta: EventMetadata):
    msg = ""
    if event.args is not None and len(event.args) > len(meta.request_args):
        msg += "expected {} arguments, got {}".format(len(meta.request_args), len(event.args))

    if event.kwargs is not None and len(event.kwargs) > len(meta.request_kwargs):
        if msg != "":
            msg += ", "

        msg += "expected {} keyword arguments, got {}".format(len(meta.request_kwargs), len(event.kwargs))

    if msg != "":
        prefix = f"error: function '{meta.func.__name__}' for topic '{meta.uri}' received invalid number of arguments. "
        prefix += msg
        raise ValueError(prefix)


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
    meta = _assemble_base_metadata(func, uri, Event, EventDetails)
    options = getattr(func, "__xconn_subscribe_options__", None)

    return EventMetadata(
        request_model=meta.request_model,
        request_args=meta.request_args,
        request_kwargs=meta.request_kwargs,
        no_args=meta.no_args,
        dynamic_model=meta.dynamic_model,
        dependencies=meta.dependencies,
        ctx_dependencies=meta.ctx_dependencies,
        async_dependencies=meta.async_dependencies,
        async_ctx_dependencies=meta.async_ctx_dependencies,
        details_field=meta.details_field,
        positional_field_name=meta.positional_field_name,
        subscribe_options=options,
        uri=meta.uri,
        func=func,
    )


def _sanitize_incoming_data(args: list, kwargs: dict, model_positional_args: list[str]):
    args = args if args is not None else []
    kwargs = kwargs if kwargs is not None else {}

    args_with_keys = dict(zip(model_positional_args, args))
    args_with_keys.update(kwargs)

    return args_with_keys


def collect_docs(uri: str, func: callable, type_: str):
    meta = _validate_procedure_function(func, uri)

    data = {"uri": uri, "type": type_}
    if meta.request_model is not None:
        data["in_model"] = meta.request_model.model_json_schema()

    if meta.response_model is not None:
        data["out_model"] = meta.response_model.model_json_schema()

    return data


def create_app(docs: list[dict], endpoint: str):
    app = web.Application()

    async def serve_schema(_):
        return web.json_response(docs)

    app.router.add_get(endpoint, serve_schema)
    return app


def select_authenticator(config: ClientConfig) -> IClientAuthenticator:
    if config.authmethod == "cryptosign" or config.authmethod == "wampcra" or config.authmethod == "ticket":
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


def validate_auth_inputs(config: ClientConfig) -> None:
    if is_non_empty(config.private_key) and is_non_empty(config.ticket):
        raise ValueError("provide only one of private key, ticket or secret")
    elif is_non_empty(config.ticket) and is_non_empty(config.secret):
        raise ValueError("provide only one of private key, ticket or secret")
    elif is_non_empty(config.private_key) and is_non_empty(config.secret):
        raise ValueError("provide only one of private key, ticket or secret")

    if config.authid is None and any(
        is_non_empty(value) for value in (config.private_key, config.ticket, config.secret)
    ):
        raise ValueError("authid is required with any of private key, ticket or secret")


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
            try:
                sock.connect((host, port))
                return True
            except (ConnectionRefusedError, socket.timeout):
                time.sleep(0.2)

    raise TimeoutError(f"Server did not start listening on {host}:{port} within {timeout} seconds.")


def handle_model_validation(model, **kwargs):
    try:
        return model(**kwargs)
    except ValidationError as e:
        raise ApplicationError("wamp.error.invalid_argument", e.json())


def ensure_caller_allowed(call_details: dict[str, Any], allowed_roles: list[str]):
    if len(allowed_roles) == 0:
        return

    role = call_details.get("caller_authrole", None)
    if role is None:
        msg = (
            "Router did not send call details hence the authrole of the caller cannot be determined."
            f" The caller must have one of following roles '{allowed_roles}'"
        )
        raise ApplicationError("wamp.error.internal_error", msg)

    if role not in allowed_roles:
        msg = f"The caller must have one of following roles '{allowed_roles}' got={role}"
        raise ApplicationError("wamp.error.not_authorized", msg)


def assemble_call_details(uri: str, meta: ProcedureMetadata, invocation: Invocation):
    details = {}
    if meta.details_field is not None:
        if not invocation.details:
            msg = f"Endpoint for procedure {uri} expects CallDetails but router did not send them"
            raise ApplicationError("wamp.error.internal_error", msg)

        details[meta.details_field] = CallDetails(invocation.details)

    return details


def assemble_event_details(uri: str, meta: EventMetadata, event: Event):
    details = {}
    if meta.details_field is not None:
        if not event.details:
            msg = f"Endpoint for topic {uri} expects EventDetails but router did not send them"
            raise ApplicationError("wamp.error.internal_error", msg)

        details[meta.details_field] = CallDetails(event.details)

    return details


def import_app(app: str, directory: str = ".") -> App:
    split = app.split(":")
    if len(split) != 2:
        raise RuntimeError("invalid app argument, must be of format: module:instance")

    sys.path.append(directory)
    module = importlib.import_module(split[0])
    app: App = getattr(module, split[1])
    if not isinstance(app, App):
        raise RuntimeError(f"app instance is of unknown type {type(app)}")

    return app


def connect(app: str, config: ClientConfig, start_router: bool = False, directory: str = "."):
    imported_app = import_app(app, directory)
    if imported_app.execution_mode == ExecutionMode.ASYNC:
        from xconn._client.async_ import _connect_async
        from xconn.utils import run

        run(_connect_async(imported_app, config, start_router=start_router))
    elif imported_app.execution_mode == ExecutionMode.SYNC:
        from xconn._client.sync import _connect_sync

        _connect_sync(imported_app, config, start_router=start_router)
    else:
        raise RuntimeError(f"execution mode {imported_app.execution_mode} not supported yet")


def load_config_from_env(args: CommandArgs) -> ClientConfig:
    if args.url is not None and args.url != "":
        url = args.url
    else:
        url = os.environ.get("XCORN_URL", None)
        if url is None or url == "":
            print("XCORN_URL missing in environment variable")
            exit(1)

    if args.realm is not None and args.realm != "":
        realm = args.realm
    else:
        realm = os.environ.get("XCORN_REALM", None)
        if realm is None or realm == "":
            print("XCORN_REALM missing in environment variable")
            exit(1)

    return ClientConfig(
        url=url,
        realm=realm,
        authid=os.environ.get("XCORN_AUTHID", args.authid),
        secret=os.environ.get("XCORN_SECRET", args.secret),
        ticket=os.environ.get("XCORN_TICKET", args.ticket),
        private_key=os.environ.get("XCORN_PRIVATE_KEY", args.private_key),
    )


def load_config_from_dot_env(args: CommandArgs):
    if args.config_file is not None and args.config_file != "":
        load_dotenv(args.config_file)
    elif os.path.exists(os.path.join(os.getcwd(), ".env")):
        load_dotenv()
    else:
        print(".env file doesn't exist. You may use --config-file flag to specify a env file.")
        exit(1)

    return load_config_from_env(args)


def load_config_from_yaml(args: CommandArgs) -> ClientConfig:
    with open(args.config_file) as f:
        config_raw = yaml.safe_load(f)

    for name, value in args.model_dump().items():
        if value is not None:
            config_raw[name] = value

    return ClientConfig(**config_raw)


def load_config_from_file(args: CommandArgs) -> ClientConfig:
    if args.config_file is not None:
        if not os.path.exists(args.config_file):
            raise FileNotFoundError(args.config_file)

    try:
        return load_config_from_yaml(args)
    except Exception:
        return load_config_from_dot_env(args)


def update_config_from_cli(config: ClientConfig, command_args: CommandArgs) -> ClientConfig:
    command_args_dict = command_args.model_dump(exclude_none=True)

    for key, value in command_args_dict.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return config
