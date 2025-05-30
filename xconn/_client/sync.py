import inspect
import threading

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


def connect_sync(app: App, config: ClientConfig, serve_schema: bool = False, start_router: bool = False):
    if start_router:
        threading.Thread(target=start_server_sync, args=(config,), daemon=True).start()

    auth = select_authenticator(config)
    client = Client(authenticator=auth)

    session = client.connect(config.url, config.realm)
    print("connected", session.base_session.realm)

    app.set_session(session)
    docs = []

    for uri, func in app.procedures.items():
        register_sync(session, uri, func)
        docs.append(collect_docs(uri, func, "procedure"))

    for uri, func in app.topics.items():
        subscribe_sync(session, uri, func)
        docs.append(collect_docs(uri, func, "topic"))

    if serve_schema:
        threading.Thread(
            target=serve_schema_sync, args=(config.schema_host, config.schema_port, docs), daemon=True
        ).start()


def register_sync(session: Session, uri: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must not be a coroutine")

    model, response_model, positional_args, response_positional_args = _validate_procedure_function(func, uri)

    def _handle_invocation(invocation: Invocation) -> Result:
        if model is not None:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, positional_args)

            result = func(model(**kwargs))
            return _handle_result(result, response_model, response_positional_args)

        result = func(invocation)
        return _handle_result(result, response_model, response_positional_args)

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
