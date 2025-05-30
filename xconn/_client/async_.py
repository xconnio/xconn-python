import inspect

from xconn import App
from xconn._client.helpers import (
    _validate_procedure_function,
    _validate_topic_function,
    _handle_result,
    _sanitize_incoming_data,
    collect_docs,
    serve_schema_async,
)
from xconn._client.types import ClientConfig
from xconn.client import AsyncClient
from xconn.async_session import AsyncSession
from xconn.types import Event, Invocation, Result


async def connect_async(app: App, config: ClientConfig, serve_schema=False):
    client = AsyncClient()
    session = await client.connect(config.url, config.realm)
    app.set_session(session)

    docs = []

    for uri, func in app.procedures.items():
        docs.append(collect_docs(uri, func, "procedure"))
        await register_async(session, uri, func)

    for uri, func in app.topics.items():
        docs.append(collect_docs(uri, func, "topic"))
        await subscribe_async(session, uri, func)

    if serve_schema:
        await serve_schema_async(config.schema_host, config.schema_port, docs)


async def register_async(session: AsyncSession, uri: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must be a coroutine")

    model, response_model, positional_args, response_positional_args = _validate_procedure_function(func, uri)

    async def _handle_invocation(invocation: Invocation) -> Result:
        if model is not None:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, positional_args)

            result = await func(model(**kwargs))
            return _handle_result(result, response_model, response_positional_args)

        result = await func(invocation)
        return _handle_result(result, response_model, response_positional_args)

    await session.register(uri, _handle_invocation)


async def subscribe_async(session: AsyncSession, topic: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    async def _handle_event(event: Event) -> None:
        if model is not None:
            kwargs = _sanitize_incoming_data(event.args, event.kwargs, positional_args)

            await func(model(**kwargs))

        await func(event)

    await session.subscribe(topic, _handle_event)
