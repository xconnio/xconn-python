import inspect

from xconn import App
from xconn._client.helpers import (
    _validate_procedure_function,
    _validate_topic_function,
    _handle_result,
    _sanitize_incoming_data,
)
from xconn._client.types import ClientConfig
from xconn.client import Client
from xconn.session import Session
from xconn.types import Event, Invocation, Result


def connect_sync(app: App, config: ClientConfig):
    client = Client()
    session = client.connect(config.url, config.realm)
    app.set_session(session)

    for uri, func in app.procedures.items():
        register_sync(session, uri, func)

    for uri, func in app.topics.items():
        subscribe_sync(session, uri, func)

    print("connected", session.base_session.realm)


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


def subscribe_sync(session: Session, topic: str, func: callable):
    if inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must not be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    def _handle_event(event: Event):
        if model is not None:
            kwargs = _sanitize_incoming_data(event.args, event.kwargs, positional_args)
            func(model(**kwargs))

        func(event)

    session.subscribe(topic, _handle_event)
