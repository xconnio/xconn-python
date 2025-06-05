import asyncio
import inspect

from xconn import App
from xconn._client.helpers import (
    _validate_procedure_function,
    _validate_topic_function,
    _handle_result,
    _sanitize_incoming_data,
    collect_docs,
    serve_schema_async,
    select_authenticator,
    start_server_async,
    handle_model_validation,
)
from xconn._client.types import ClientConfig
from xconn.client import AsyncClient
from xconn.async_session import AsyncSession
from xconn.types import Event, Invocation, Result


async def _setup(app: App, session: AsyncSession):
    app.set_session(session)

    for uri, func in app.procedures.items():
        await register_async(session, uri, func)

    for uri, func in app.topics.items():
        await subscribe_async(session, uri, func)


async def connect_async(app: App, config: ClientConfig, serve_schema=True, start_router: bool = False):
    if start_router:
        await start_server_async(config)

    auth = select_authenticator(config)
    client = AsyncClient(authenticator=auth, ws_config=config.websocket_config)

    async def wait_and_connect(wait=10):
        print(f"reconnecting in {wait} seconds...")
        await asyncio.sleep(wait)

        try:
            new_session = await client.connect(config.url, config.realm, on_connect, on_disconnect)
        except Exception as e:
            print(e)

            await wait_and_connect(wait)
            return

        await _setup(app, new_session)

    async def on_connect():
        print("connected", config.realm)

    async def on_disconnect():
        print("disconnected", config.realm)
        await wait_and_connect()

    session = await client.connect(config.url, config.realm, on_connect, on_disconnect)
    await _setup(app, session)

    if serve_schema:
        docs = []

        for uri, func in app.procedures.items():
            docs.append(collect_docs(uri, func, "procedure"))

        for uri, func in app.topics.items():
            docs.append(collect_docs(uri, func, "topic"))

        await serve_schema_async(config.schema_host, config.schema_port, docs)


async def register_async(session: AsyncSession, uri: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for procedure '{uri}' must be a coroutine")

    meta = _validate_procedure_function(func, uri)

    async def _handle_invocation(invocation: Invocation) -> Result:
        if meta.dynamic_model:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)
            handle_model_validation(meta.request_model, **kwargs)
            result = await func(**kwargs)
            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.request_model is not None:
            kwargs = _sanitize_incoming_data(invocation.args, invocation.kwargs, meta.request_args)
            model = handle_model_validation(meta.request_model, **kwargs)
            result = await func(model)

            return _handle_result(result, meta.response_model, meta.response_args)
        elif meta.no_args:
            result = await func()
            return _handle_result(result, meta.response_model, meta.response_args)
        else:
            result = await func(invocation)
            return _handle_result(result, meta.response_model, meta.response_args)

    await session.register(uri, _handle_invocation)
    print(f"Registered procedure {uri}")


async def subscribe_async(session: AsyncSession, topic: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    async def _handle_event(event: Event) -> None:
        if model is not None:
            kwargs = _sanitize_incoming_data(event.args, event.kwargs, positional_args)
            try:
                await func(model(**kwargs))
            except Exception as e:
                print(e)

            return

        try:
            await func(event)
        except Exception as e:
            print(e)

    await session.subscribe(topic, _handle_event)
    print(f"Subscribed topic {topic}")
