import inspect
from multiprocessing import Process
import threading
import time

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

    auth = select_authenticator(config)
    client = Client(authenticator=auth, ws_config=config.websocket_config)

    def wait_and_connect(wait=10):
        print(f"reconnecting in {wait} seconds...")
        time.sleep(wait)

        try:
            new_session = client.connect(config.url, config.realm, on_connect, on_disconnect)
        except Exception as e:
            print(e)

            wait_and_connect(wait)
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


def register_sync(session: Session, uri: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must not be a coroutine")

    meta = _validate_procedure_function(func, uri)

    def _handle_invocation(invocation: Invocation) -> Result:
        if meta.dynamic_model:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)
            meta.request_model(**kwargs)
            result = func(**kwargs)
            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.request_model is not None:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)

            result = func(meta.request_model(**kwargs))
            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.no_args:
            result = func()
            return _handle_result(result, meta.response_model, meta.response_args)
        else:
            result = func(invocation)
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
