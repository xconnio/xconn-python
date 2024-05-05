import asyncio
from concurrent.futures import Future
from threading import Thread
from typing import Callable, Any

from wampproto import messages, idgen, session

from xconn import types


class Session:
    def __init__(self, base_session: types.BaseSession):
        # RPC data structures
        self.call_requests: dict[int, Future[types.Result]] = {}
        self.register_requests: dict[int, types.RegisterRequest] = {}
        self.registrations: dict[int, Callable[[types.Invocation], types.Result]] = {}
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

        thread = Thread(target=self.wait)
        thread.start()

    def wait(self):
        while True:
            try:
                data = self.base_session.receive()
            except Exception:
                break

            self.process_incoming_message(self.session.receive(data))

    def process_incoming_message(self, msg: messages.Message):
        if isinstance(msg, messages.Registered):
            request = self.register_requests.pop(msg.request_id)
            self.registrations[msg.registration_id] = request.endpoint
            request.future.set_result(types.Registration(msg.registration_id))
        elif isinstance(msg, messages.UnRegistered):
            request = self.unregister_requests.pop(msg.request_id)
            del self.registrations[request.registration_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Result):
            request = self.call_requests.pop(msg.request_id)
            request.set_result(types.Result(msg.args, msg.kwargs, msg.options))
        elif isinstance(msg, messages.Invocation):
            endpoint = self.registrations[msg.registration_id]
            result = endpoint(msg)
            data = self.session.send_message(messages.Yield(msg.request_id, result.args, result.kwargs, result.details))
            self.base_session.send(data)
        elif isinstance(msg, messages.Subscribed):
            request = self.subscribe_requests.pop(msg.request_id)
            self.subscriptions[msg.subscription_id] = request.endpoint
            request.future.set_result(types.Subscription(msg.subscription_id))
        elif isinstance(msg, messages.UnSubscribed):
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
            pass
        else:
            raise ValueError("received unknown message")

    def call(self, procedure: str, args: list[Any] = None, kwargs: dict = None, options: dict = None) -> types.Result:
        call = messages.Call(self.idgen.next(), procedure, args, kwargs, options)
        data = self.session.send_message(call)

        f = Future()
        self.call_requests[call.request_id] = f
        self.base_session.send(data)

        return f.result()

    def register(self, procedure: str, endpoint: Callable[[types.Invocation], types.Result]) -> types.Registration:
        register = messages.Register(self.idgen.next(), procedure)
        data = self.session.send_message(register)

        f: Future[types.Registration] = Future()
        self.register_requests[register.request_id] = types.RegisterRequest(f, endpoint)
        self.base_session.send(data)

        return f.result()

    def unregister(self, reg: types.Registration):
        unregister = messages.UnRegister(self.idgen.next(), reg.registration_id)
        data = self.session.send_message(unregister)

        f: Future = Future()
        self.unregister_requests[unregister.request_id] = types.UnregisterRequest(f, reg.registration_id)
        self.base_session.send(data)

        f.result()

    def subscribe(self, topic: str, endpoint: Callable[[types.Event], None]) -> types.Subscription:
        subscribe = messages.Subscribe(self.idgen.next(), topic)
        data = self.session.send_message(subscribe)

        f: Future[types.Subscription] = Future()
        self.subscribe_requests[subscribe.request_id] = types.SubscribeRequest(f, endpoint)
        self.base_session.send(data)

        return f.result()

    def unsubscribe(self, sub: types.Subscription):
        unsubscribe = messages.UnSubscribe(self.idgen.next(), sub.subscription_id)
        data = self.session.send_message(unsubscribe)

        f: Future = Future()
        self.unsubscribe_requests[unsubscribe.request_id] = types.UnsubscribeRequest(f, sub.subscription_id)
        self.base_session.send(data)

        f.result()

    def publish(self, topic: str, args: list[Any] = None, kwargs: dict = None, options: dict = None):
        publish = messages.Publish(self.idgen.next(), topic, args, kwargs, options)
        data = self.session.send_message(publish)

        if options is not None and options.get("acknowledge", True):
            f: Future = Future()
            self.publish_requests[publish.request_id] = f
            self.base_session.send(data)
            return f.result()

        self.base_session.send(data)


class AsyncSession:
    def __init__(self, base_session: types.IAsyncBaseSession):
        # RPC data structures
        self.call_requests: dict[int, Future[types.Result]] = {}
        self.register_requests: dict[int, types.RegisterRequest] = {}
        self.registrations: dict[int, Callable[[types.Invocation], types.Result]] = {}
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

        loop = asyncio.get_event_loop()
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
        elif isinstance(msg, messages.UnRegistered):
            request = self.unregister_requests.pop(msg.request_id)
            del self.registrations[request.registration_id]
            request.future.set_result(None)
        elif isinstance(msg, messages.Result):
            request = self.call_requests.pop(msg.request_id)
            request.set_result(types.Result(msg.args, msg.kwargs, msg.options))
        elif isinstance(msg, messages.Invocation):
            endpoint = self.registrations[msg.registration_id]
            result = endpoint(msg)
            data = self.session.send_message(messages.Yield(msg.request_id, result.args, result.kwargs, result.details))
            await self.base_session.send(data)
        elif isinstance(msg, messages.Subscribed):
            request = self.subscribe_requests.pop(msg.request_id)
            self.subscriptions[msg.subscription_id] = request.endpoint
            request.future.set_result(types.Subscription(msg.subscription_id))
        elif isinstance(msg, messages.UnSubscribed):
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
            pass
        else:
            raise ValueError("received unknown message")

    async def register(
        self, procedure: str, endpoint: Callable[[types.Invocation], types.Result]
    ) -> Future[types.Registration]:
        register = messages.Register(self.idgen.next(), procedure, options={})
        data = self.session.send_message(register)

        f: Future[types.Registration] = Future()
        self.register_requests[register.request_id] = types.RegisterRequest(f, endpoint)
        await self.base_session.send(data)

        return f
