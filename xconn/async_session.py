import asyncio
import inspect
from asyncio import Future, get_event_loop
from typing import Callable, Union, Awaitable, Any

from wampproto import messages, idgen, session

from xconn import types, uris as xconn_uris, exception
from xconn.exception import ApplicationError
from xconn.helpers import exception_from_error


def register(
    wamp_session: session.WAMPSession,
    id_generator: idgen.SessionScopeIDGenerator,
    register_requests: dict[int, types.RegisterRequest],
    procedure: str,
    invocation_handler: Callable | Callable[[types.Invocation], types.Result],
    options: dict | types.RegisterOptions | None = None,
) -> types.RegisterResponse:
    register_msg = messages.Register(messages.RegisterFields(id_generator.next(), procedure, options=options))
    data = wamp_session.send_message(register_msg)

    f: Future[types.Registration] = Future()
    register_requests[register_msg.request_id] = types.RegisterRequest(f, invocation_handler)

    return types.RegisterResponse(data, f)


def call(
    wamp_session: session.WAMPSession,
    id_generator: idgen.SessionScopeIDGenerator,
    call_requests: dict[int, Future[types.Result]],
    procedure: str,
    *args,
    **kwargs,
) -> types.CallResponse:
    options = kwargs.pop("options", None)
    call_msg = messages.Call(messages.CallFields(id_generator.next(), procedure, args, kwargs, options=options))
    data = wamp_session.send_message(call_msg)

    f = Future()
    call_requests[call_msg.request_id] = f

    return types.CallResponse(data, f)


class AsyncSession:
    def __init__(self, base_session: types.IAsyncBaseSession):
        # RPC data structures
        self.call_requests: dict[int, Future[types.Result]] = {}
        self.register_requests: dict[int, types.RegisterRequest] = {}
        self.registrations: dict[
            int,
            Union[Callable[[types.Invocation], types.Result], Callable[[types.Invocation], Awaitable[types.Result]]],
        ] = {}
        self.unregister_requests: dict[int, types.UnregisterRequest] = {}

        # PubSub data structures
        self.publish_requests: dict[int, Future[None]] = {}
        self.subscribe_requests: dict[int, types.SubscribeRequest] = {}
        self.subscriptions: dict[int, Callable[[types.Event], Awaitable[None]]] = {}
        self.unsubscribe_requests: dict[int, types.UnsubscribeRequest] = {}

        self.goodbye_request = Future()

        # ID generator
        self.idgen = idgen.SessionScopeIDGenerator()

        self.base_session = base_session

        # initialize the sans-io wamp session
        self.session = session.WAMPSession(base_session.serializer)

        self._disconnect_callback: list[Callable[[], Awaitable[None]] | None] = []

        loop = get_event_loop()
        self.wait_task = loop.create_task(self.wait())

    async def wait(self):
        while await self.base_session.transport.is_connected():
            try:
                data = await self.base_session.receive()
            except Exception as e:
                print(e)
                break

            await self.process_incoming_message(self.session.receive(data))

        for callback in self._disconnect_callback:
            await callback()

    async def process_incoming_message(self, msg: messages.Message):
        if isinstance(msg, messages.Registered):
            request = self.register_requests.pop(msg.request_id)
            self.registrations[msg.registration_id] = request.endpoint
            request.future.set_result(types.Registration(msg.registration_id))
        elif isinstance(msg, messages.Unregistered):
            request = self.unregister_requests.pop(msg.request_id)
            del self.registrations[request.registration_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Result):
            request = self.call_requests.pop(msg.request_id)
            request.set_result(types.Result(msg.args, msg.kwargs, msg.options))
        elif isinstance(msg, messages.Invocation):
            try:
                endpoint = self.registrations[msg.registration_id]
                result = await endpoint(types.Invocation(msg.args, msg.kwargs, msg.details))

                if result is None:
                    data = self.session.send_message(messages.Yield(messages.YieldFields(msg.request_id)))
                elif isinstance(result, types.Result):
                    data = self.session.send_message(
                        messages.Yield(messages.YieldFields(msg.request_id, result.args, result.kwargs, result.details))
                    )
                else:
                    message = "Endpoint returned invalid result type. Expected types.Result or None, got: " + str(
                        type(result)
                    )
                    msg_to_send = messages.Error(
                        messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_INTERNAL_ERROR, [message])
                    )
                    data = self.session.send_message(msg_to_send)

                await self.base_session.send(data)
            except ApplicationError as e:
                msg_to_send = messages.Error(messages.ErrorFields(msg.TYPE, msg.request_id, e.message, e.args))
                data = self.session.send_message(msg_to_send)
                await self.base_session.send(data)
            except Exception as e:
                msg_to_send = messages.Error(
                    messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_RUNTIME_ERROR, [e.__str__()])
                )
                data = self.session.send_message(msg_to_send)
                await self.base_session.send(data)
        elif isinstance(msg, messages.Subscribed):
            request = self.subscribe_requests.pop(msg.request_id)
            self.subscriptions[msg.subscription_id] = request.endpoint
            request.future.set_result(types.Subscription(msg.subscription_id))
        elif isinstance(msg, messages.Unsubscribed):
            request = self.unsubscribe_requests.pop(msg.request_id)
            del self.subscriptions[request.subscription_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Published):
            request = self.publish_requests.pop(msg.request_id)
            request.set_result(None)
        elif isinstance(msg, messages.Event):
            endpoint = self.subscriptions[msg.subscription_id]
            try:
                await endpoint(types.Event(msg.args, msg.kwargs, msg.details))
            except Exception as e:
                print(e)
        elif isinstance(msg, messages.Error):
            match msg.message_type:
                case messages.Call.TYPE:
                    call_request = self.call_requests.pop(msg.request_id)
                    call_request.set_exception(exception_from_error(msg))
                case messages.Register.TYPE:
                    register_request = self.register_requests.pop(msg.request_id)
                    register_request.future.set_exception(exception_from_error(msg))
                case messages.Unregister.TYPE:
                    unregister_request = self.unregister_requests.pop(msg.request_id)
                    unregister_request.future.set_exception(exception_from_error(msg))
                case messages.Subscribe.TYPE:
                    subscribe_request = self.subscribe_requests.pop(msg.request_id)
                    subscribe_request.future.set_exception(exception_from_error(msg))
                case messages.Unsubscribe.TYPE:
                    unsubscribe_request = self.unsubscribe_requests.pop(msg.request_id)
                    unsubscribe_request.future.set_exception(exception_from_error(msg))
                case messages.Publish.TYPE:
                    publish_request = self.publish_requests.pop(msg.request_id)
                    publish_request.set_exception(exception_from_error(msg))
                case _:
                    raise exception.ProtocolError(msg.__str__())
        elif isinstance(msg, messages.Goodbye):
            self.goodbye_request.set_result(None)
        else:
            raise ValueError("received unknown message")

    async def register(
        self,
        procedure: str,
        invocation_handler: Callable[[types.Invocation], Awaitable[types.Result]],
        options: dict = None,
    ) -> types.Registration:
        if not inspect.iscoroutinefunction(invocation_handler):
            raise RuntimeError(
                f"function {invocation_handler.__name__} for procedure '{procedure}' must be a coroutine"
            )

        register_response = register(
            self.session, self.idgen, self.register_requests, procedure, invocation_handler, options
        )
        await self.base_session.send(register_response.data)

        return await register_response.future

    async def unregister(self, reg: types.Registration):
        unregister = messages.Unregister(messages.UnregisterFields(self.idgen.next(), reg.registration_id))
        data = self.session.send_message(unregister)

        f: Future = Future()
        self.unregister_requests[unregister.request_id] = types.UnregisterRequest(f, reg.registration_id)
        await self.base_session.send(data)

        return await f

    async def call(self, procedure: str, *args, **kwargs) -> types.Result:
        call_response = call(self.session, self.idgen, self.call_requests, procedure, *args, **kwargs)

        await self.base_session.send(call_response.data)

        return await call_response.future

    async def subscribe(
        self, topic: str, event_handler: Callable[[types.Event], Awaitable[None]], options: dict | None = None
    ) -> types.Subscription:
        if not inspect.iscoroutinefunction(event_handler):
            raise RuntimeError(f"function {event_handler.__name__} for topic '{topic}' must be a coroutine")

        subscribe = messages.Subscribe(messages.SubscribeFields(self.idgen.next(), topic, options=options))
        data = self.session.send_message(subscribe)

        f: Future[types.Subscription] = Future()
        self.subscribe_requests[subscribe.request_id] = types.SubscribeRequest(f, event_handler)
        await self.base_session.send(data)

        return await f

    async def unsubscribe(self, sub: types.Subscription) -> None:
        unsubscribe = messages.Unsubscribe(messages.UnsubscribeFields(self.idgen.next(), sub.subscription_id))
        data = self.session.send_message(unsubscribe)

        f: Future = Future()
        self.unsubscribe_requests[unsubscribe.request_id] = types.UnsubscribeRequest(f, sub.subscription_id)
        await self.base_session.send(data)

        return await f

    async def publish(
        self, topic: str, args: list[Any] | None = None, kwargs: dict | None = None, options: dict | None = None
    ) -> None:
        publish = messages.Publish(messages.PublishFields(self.idgen.next(), topic, args, kwargs, options))
        data = self.session.send_message(publish)

        if options is not None and options.get("acknowledge", False):
            f: Future = Future()
            self.publish_requests[publish.request_id] = f
            await self.base_session.send(data)
            return await f

        await self.base_session.send(data)

    async def leave(self) -> None:
        self.goodbye_request = Future()

        goodbye = messages.Goodbye(messages.GoodbyeFields({}, xconn_uris.CLOSE_REALM))
        data = self.session.send_message(goodbye)
        await self.base_session.send(data)

        try:
            await asyncio.wait_for(self.goodbye_request, timeout=10)
        except asyncio.TimeoutError:
            pass

        self.wait_task.cancel()
        try:
            await self.wait_task
        except asyncio.CancelledError:
            pass

        if await self.base_session.transport.is_connected():
            await self.base_session.close()

    async def ping(self, timeout: int = 10) -> float:
        return await self.base_session.transport.ping(timeout)

    def on_disconnect(self, callback: Callable[[], Awaitable[None]]) -> None:
        if callback is not None:
            self._disconnect_callback.append(callback)
