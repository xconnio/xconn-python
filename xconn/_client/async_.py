import inspect

from xconn import App
from xconn._client.helpers import _validate_procedure_function, _validate_topic_function, _handle_result
from xconn._client.types import ClientConfig
from xconn.client import AsyncClient
from xconn.async_session import AsyncSession
from xconn.exception import ApplicationError
from xconn.types import Event, Invocation, Result


async def connect_async(app: App, config: ClientConfig):
    client = AsyncClient()
    session = await client.connect(config.url, config.realm)
    app.set_session(session)

    for uri, func in app.procedures.items():
        await register_async(session, uri, func)

    for uri, func in app.topics.items():
        await subscribe_async(session, uri, func)

    print("connected", session.base_session.realm)


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


async def subscribe_async(session: AsyncSession, topic: str, func: callable):
    if not inspect.iscoroutinefunction(func):
        raise RuntimeError(f"function {func.__name__} for topic '{topic}' must be a coroutine")

    model, positional_args = _validate_topic_function(func, topic)

    async def _handle_event(event: Event) -> None:
        if model is not None:
            args = event.args if event.args is not None else []
            kwargs = event.kwargs if event.kwargs is not None else {}

            if len(args) != len(positional_args):
                raise ApplicationError("foo.bar")

            args_with_keys = dict(zip(positional_args, args))

            await func(model(**args_with_keys, **kwargs))

        await func(event)

    await session.subscribe(topic, _handle_event)
