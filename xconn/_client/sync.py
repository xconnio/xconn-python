import contextlib
import random
import inspect
from multiprocessing import Process
import threading
import time
from typing import Any, Generator
from urllib.parse import urlparse

from xconn import App
from xconn._client.helpers import (
    _validate_procedure_function,
    _validate_topic_function,
    _handle_result,
    _sanitize_incoming_data,
    collect_docs,
    serve_schema_sync,
    select_authenticator,
    start_server_sync,
    wait_for_server,
    handle_model_validation,
    ensure_caller_allowed,
    INITIAL_WAIT,
    MAX_WAIT,
    ProcedureMetadata,
)
from xconn._client.types import ClientConfig
from xconn.client import Client
from xconn.session import Session
from xconn.types import Event, Invocation, Result


def _setup(app: App, session: Session):
    app.set_session(session)

    for uri, func in app.procedures.items():
        register_sync(session, uri, func)

    for uri, func in app.topics.items():
        subscribe_sync(session, uri, func)


def connect_sync(app: App, config: ClientConfig, serve_schema: bool = False, start_router: bool = False):
    if start_router:
        threading.Thread(target=start_server_sync, args=(config,), daemon=True).start()

    ws_url = urlparse(config.url)
    wait_for_server(ws_url.hostname, ws_url.port, 10)

    auth = select_authenticator(config)
    client = Client(authenticator=auth, ws_config=config.websocket_config)

    def wait_and_connect(previous_wait: float = INITIAL_WAIT):
        next_wait = min(random.uniform(INITIAL_WAIT, previous_wait * 3), MAX_WAIT)
        print(f"reconnecting in {next_wait:.1f} seconds...")
        time.sleep(next_wait)

        try:
            new_session = client.connect(config.url, config.realm, on_connect, on_disconnect)
        except Exception as e:
            print(e)

            wait_and_connect(next_wait)
            return

        _setup(app, new_session)

    def on_connect():
        print("connected", config.realm)

    def on_disconnect():
        print("disconnected", config.realm)
        wait_and_connect()

    session = client.connect(config.url, config.realm, on_connect, on_disconnect)
    _setup(app, session)

    if serve_schema:
        docs = []

        for uri, func in app.procedures.items():
            docs.append(collect_docs(uri, func, "procedure"))

        for uri, func in app.topics.items():
            docs.append(collect_docs(uri, func, "topic"))

        docs_process = Process(target=serve_schema_sync, args=(config.schema_host, config.schema_port, docs))
        docs_process.start()


@contextlib.contextmanager
def resolve_dependencies(meta: ProcedureMetadata) -> Generator[dict[Any, Any], Any, None]:
    result = {}

    for key, value in meta.dependencies.items():
        result[key] = value()

    with contextlib.ExitStack() as stack:
        for name, dependency in meta.ctx_dependencies.items():
            result[name] = stack.enter_context(dependency())

        yield result


def register_sync(session: Session, uri: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must not be a coroutine")

    meta = _validate_procedure_function(func, uri)

    def _handle_invocation(invocation: Invocation) -> Result:
        ensure_caller_allowed(invocation.details, meta.allowed_roles)

        if meta.dynamic_model:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)
            handle_model_validation(meta.request_model, **kwargs)

            with resolve_dependencies(meta) as deps:
                result = func(**kwargs, **deps)

            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.request_model is not None:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)
            model = handle_model_validation(meta.request_model, **kwargs)

            with resolve_dependencies(meta) as deps:
                result = func(model, **deps)

            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.no_args:
            with resolve_dependencies(meta) as deps:
                result = func(**deps)

            return _handle_result(result, meta.response_model, meta.response_args)
        else:
            with resolve_dependencies(meta) as deps:
                result = func(invocation, **deps)

            return _handle_result(result, meta.response_model, meta.response_args)

    session.register(uri, _handle_invocation)
    print(f"Registered procedure {uri}")


def subscribe_sync(session: Session, topic: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must not be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    def _handle_event(event: Event):
        if model is not None:
            kwargs = _sanitize_incoming_data(event.args, event.kwargs, positional_args)

            try:
                func(model(**kwargs))
            except Exception as e:
                print(e)

            return

        try:
            func(event)
        except Exception as e:
            print(e)

    session.subscribe(topic, _handle_event)
    print(f"Subscribed topic {topic}")
