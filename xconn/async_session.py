from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from asyncio import Future, get_event_loop
from typing import Callable, Union, Awaitable, Any

from wampproto import messages, idgen, session

from xconn import types, uris as xconn_uris, exception
from xconn.exception import ApplicationError
from xconn.helpers import exception_from_error


@dataclass
class RegisterRequest:
    future: Future[Registration]
    endpoint: Callable | Callable[[types.Invocation], Awaitable[types.Result]]


class Registration:
    def __init__(self, registration_id: int, session: AsyncSession):
        self.registration_id = registration_id
        self._session = session

    async def unregister(self) -> None:
        if not await self._session._base_session.transport.is_connected():
            raise Exception("cannot unregister procedure: session not established")

        unregister = messages.Unregister(messages.UnregisterFields(self._session._idgen.next(), self.registration_id))
        data = self._session._session.send_message(unregister)

        f: Future = Future()
        self._session._unregister_requests[unregister.request_id] = types.UnregisterRequest(f, self.registration_id)
        await self._session._base_session.send(data)

        return await f


@dataclass
class SubscribeRequest:
    future: Future[Subscription]
    endpoint: Callable[[types.Event], Awaitable[None]]


class Subscription:
    def __init__(self, subscription_id: int, session: AsyncSession):
        self.subscription_id = subscription_id
        self._session = session

    async def unsubscribe(self) -> None:
        if not await self._session._base_session.transport.is_connected():
            raise Exception("cannot unsubscribe topic: session not established")

        unsubscribe = messages.Unsubscribe(
            messages.UnsubscribeFields(self._session._idgen.next(), self.subscription_id)
        )
        data = self._session._session.send_message(unsubscribe)

        f: Future = Future()
        self._session._unsubscribe_requests[unsubscribe.request_id] = types.UnsubscribeRequest(f, self.subscription_id)
        await self._session._base_session.send(data)

        return await f


class AsyncSession:
    def __init__(self, base_session: types.IAsyncBaseSession):
        # RPC data structures
        self._call_requests: dict[int, Future[types.Result]] = {}
        self._register_requests: dict[int, RegisterRequest] = {}
        self._registrations: dict[
            int,
            Union[Callable[[types.Invocation], types.Result], Callable[[types.Invocation], Awaitable[types.Result]]],
        ] = {}
        self._unregister_requests: dict[int, types.UnregisterRequest] = {}

        # PubSub data structures
        self._publish_requests: dict[int, Future[None]] = {}
        self._subscribe_requests: dict[int, SubscribeRequest] = {}
        self._subscriptions: dict[int, Callable[[types.Event], Awaitable[None]]] = {}
        self._unsubscribe_requests: dict[int, types.UnsubscribeRequest] = {}

        self._goodbye_request = Future()

        # ID generator
        self._idgen = idgen.SessionScopeIDGenerator()

        self._base_session = base_session

        # initialize the sans-io wamp session
        self._session = session.WAMPSession(base_session.serializer)

        self._disconnect_callback: list[Callable[[], Awaitable[None]] | None] = []

        loop = get_event_loop()
        self.wait_task = loop.create_task(self._wait())

    async def _wait(self):
        while await self._base_session.transport.is_connected():
            try:
                data = await self._base_session.receive()
            except Exception as e:
                print(e)
                break

            await self._process_incoming_message(self._session.receive(data))

        for callback in self._disconnect_callback:
            await callback()

    async def _process_incoming_message(self, msg: messages.Message):
        if isinstance(msg, messages.Registered):
            request = self._register_requests.pop(msg.request_id)
            self._registrations[msg.registration_id] = request.endpoint
            request.future.set_result(Registration(msg.registration_id, self))
        elif isinstance(msg, messages.Unregistered):
            request = self._unregister_requests.pop(msg.request_id)
            del self._registrations[request.registration_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Result):
            request = self._call_requests.pop(msg.request_id)
            request.set_result(types.Result(msg.args, msg.kwargs, msg.details))
        elif isinstance(msg, messages.Invocation):
            try:
                endpoint = self._registrations[msg.registration_id]
                result = await endpoint(types.Invocation(msg.args, msg.kwargs, msg.details))

                if result is None:
                    data = self._session.send_message(messages.Yield(messages.YieldFields(msg.request_id)))
                elif isinstance(result, types.Result):
                    data = self._session.send_message(
                        messages.Yield(messages.YieldFields(msg.request_id, result.args, result.kwargs, result.details))
                    )
                else:
                    message = "Endpoint returned invalid result type. Expected types.Result or None, got: " + str(
                        type(result)
                    )
                    msg_to_send = messages.Error(
                        messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_INTERNAL_ERROR, [message])
                    )
                    data = self._session.send_message(msg_to_send)

                await self._base_session.send(data)
            except ApplicationError as e:
                msg_to_send = messages.Error(messages.ErrorFields(msg.TYPE, msg.request_id, e.message, e.args))
                data = self._session.send_message(msg_to_send)
                await self._base_session.send(data)
            except Exception as e:
                msg_to_send = messages.Error(
                    messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_RUNTIME_ERROR, [e.__str__()])
                )
                data = self._session.send_message(msg_to_send)
                await self._base_session.send(data)
        elif isinstance(msg, messages.Subscribed):
            request = self._subscribe_requests.pop(msg.request_id)
            self._subscriptions[msg.subscription_id] = request.endpoint
            request.future.set_result(Subscription(msg.subscription_id, self))
        elif isinstance(msg, messages.Unsubscribed):
            request = self._unsubscribe_requests.pop(msg.request_id)
            del self._subscriptions[request.subscription_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Published):
            request = self._publish_requests.pop(msg.request_id)
            request.set_result(None)
        elif isinstance(msg, messages.Event):
            endpoint = self._subscriptions[msg.subscription_id]
            try:
                await endpoint(types.Event(msg.args, msg.kwargs, msg.details))
            except Exception as e:
                print(e)
        elif isinstance(msg, messages.Error):
            match msg.message_type:
                case messages.Call.TYPE:
                    call_request = self._call_requests.pop(msg.request_id)
                    call_request.set_exception(exception_from_error(msg))
                case messages.Register.TYPE:
                    register_request = self._register_requests.pop(msg.request_id)
                    register_request.future.set_exception(exception_from_error(msg))
                case messages.Unregister.TYPE:
                    unregister_request = self._unregister_requests.pop(msg.request_id)
                    unregister_request.future.set_exception(exception_from_error(msg))
                case messages.Subscribe.TYPE:
                    subscribe_request = self._subscribe_requests.pop(msg.request_id)
                    subscribe_request.future.set_exception(exception_from_error(msg))
                case messages.Unsubscribe.TYPE:
                    unsubscribe_request = self._unsubscribe_requests.pop(msg.request_id)
                    unsubscribe_request.future.set_exception(exception_from_error(msg))
                case messages.Publish.TYPE:
                    publish_request = self._publish_requests.pop(msg.request_id)
                    publish_request.set_exception(exception_from_error(msg))
                case _:
                    raise exception.ProtocolError(msg.__str__())
        elif isinstance(msg, messages.Goodbye):
            self._goodbye_request.set_result(None)
        else:
            raise ValueError("received unknown message")

    async def register(
        self,
        procedure: str,
        invocation_handler: Callable[[types.Invocation], Awaitable[types.Result]],
        options: dict = None,
    ) -> Registration:
        if not inspect.iscoroutinefunction(invocation_handler):
            raise RuntimeError(
                f"function {invocation_handler.__name__} for procedure '{procedure}' must be a coroutine"
            )

        register = messages.Register(messages.RegisterFields(self._idgen.next(), procedure, options=options))
        data = self._session.send_message(register)

        f: Future[Registration] = Future()
        self._register_requests[register.request_id] = RegisterRequest(f, invocation_handler)
        await self._base_session.send(data)

        return await f

    async def call(self, procedure: str, *args, **kwargs) -> types.Result:
        options = kwargs.pop("options", None)
        call = messages.Call(messages.CallFields(self._idgen.next(), procedure, args, kwargs, options=options))
        data = self._session.send_message(call)

        f = Future()
        self._call_requests[call.request_id] = f

        await self._base_session.send(data)

        return await f

    async def subscribe(
        self, topic: str, event_handler: Callable[[types.Event], Awaitable[None]], options: dict | None = None
    ) -> Subscription:
        if not inspect.iscoroutinefunction(event_handler):
            raise RuntimeError(f"function {event_handler.__name__} for topic '{topic}' must be a coroutine")

        subscribe = messages.Subscribe(messages.SubscribeFields(self._idgen.next(), topic, options=options))
        data = self._session.send_message(subscribe)

        f: Future[Subscription] = Future()
        self._subscribe_requests[subscribe.request_id] = SubscribeRequest(f, event_handler)
        await self._base_session.send(data)

        return await f

    async def publish(
        self, topic: str, args: list[Any] | None = None, kwargs: dict | None = None, options: dict | None = None
    ) -> None:
        publish = messages.Publish(messages.PublishFields(self._idgen.next(), topic, args, kwargs, options))
        data = self._session.send_message(publish)

        if options is not None and options.get("acknowledge", False):
            f: Future = Future()
            self._publish_requests[publish.request_id] = f
            await self._base_session.send(data)
            return await f

        await self._base_session.send(data)

    async def leave(self) -> None:
        self._goodbye_request = Future()

        goodbye = messages.Goodbye(messages.GoodbyeFields({}, xconn_uris.CLOSE_REALM))
        data = self._session.send_message(goodbye)
        await self._base_session.send(data)

        try:
            await asyncio.wait_for(self._goodbye_request, timeout=10)
        except asyncio.TimeoutError:
            pass

        self.wait_task.cancel()
        try:
            await self.wait_task
        except asyncio.CancelledError:
            pass

        if await self._base_session.transport.is_connected():
            await self._base_session.close()

    async def ping(self, timeout: int = 10) -> float:
        return await self._base_session.transport.ping(timeout)

    def _on_disconnect(self, callback: Callable[[], Awaitable[None]]) -> None:
        if callback is not None:
            self._disconnect_callback.append(callback)
