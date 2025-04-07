from asyncio import Future, get_event_loop
import inspect
from typing import Callable, Union, Awaitable

from pydantic import ValidationError
from wampproto import messages, idgen, session

from xconn import types, uris as xconn_uris, exception
from xconn.helpers import exception_from_error


def register(
    wamp_session: session.WAMPSession,
    id_generator: idgen.SessionScopeIDGenerator,
    register_requests: dict[int, types.RegisterRequest],
    procedure: str,
    invocation_handler: Callable | Callable[[types.Invocation], types.Result],
    options: dict | None = None,
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
        self.subscriptions: dict[int, Callable[[types.Event], None]] = {}
        self.unsubscribe_requests: dict[int, types.UnsubscribeRequest] = {}

        # ID generator
        self.idgen = idgen.SessionScopeIDGenerator()

        self.base_session = base_session

        # initialize the sans-io wamp session
        self.session = session.WAMPSession(base_session.serializer)

        loop = get_event_loop()
        loop.create_task(self.wait())

    async def wait(self):
        while True:
            try:
                data = await self.base_session.receive()
            except Exception as e:
                print(e)
                break

            await self.process_incoming_message(self.session.receive(data))

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

                if inspect.iscoroutinefunction(endpoint):
                    if msg.args is not None and len(msg.args) != 0 and msg.kwargs is not None:
                        result = await endpoint(*msg.args, **msg.kwargs)
                    elif (msg.args is None or len(msg.args) == 0) and msg.kwargs is not None:
                        result = await endpoint(**msg.kwargs)
                    elif msg.args is not None:
                        result = await endpoint(*msg.args)
                    else:
                        result = await endpoint()
                else:
                    if msg.args is not None and len(msg.args) != 0 and msg.kwargs is not None:
                        result = endpoint(*msg.args, **msg.kwargs)
                    elif (msg.args is None or len(msg.args) == 0) and msg.kwargs is not None:
                        result = endpoint(**msg.kwargs)
                    elif msg.args is not None:
                        result = endpoint(*msg.args)
                    else:
                        result = endpoint()

                if isinstance(result, types.Result):
                    data = self.session.send_message(
                        messages.Yield(messages.YieldFields(msg.request_id, result.args, result.kwargs, result.details))
                    )
                else:
                    data = self.session.send_message(messages.Yield(messages.YieldFields(msg.request_id)))
                await self.base_session.send(data)
            except ValidationError as e:
                msg_to_send = messages.Error(
                    messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_INVALID_ARGUMENT, [e.__str__()])
                )
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
            endpoint(types.Event(msg.args, msg.kwargs, msg.details))
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
        else:
            raise ValueError("received unknown message")

    async def register(
        self, procedure: str, invocation_handler: Callable[[types.Invocation], types.Result], options: dict = None
    ) -> types.Registration:
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
        self, topic: str, event_handler: Callable[[types.Event], None], options: dict = None
    ) -> types.Subscription:
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
