from concurrent.futures import Future
from threading import Thread
from typing import Callable, Any

from wampproto import messages, idgen, session, uris

from xconn import types, exception, uris as xconn_uris
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

        self.goodbye_request = Future()

        # ID generator
        self.idgen = idgen.SessionScopeIDGenerator()

        self.base_session = base_session

        # initialize the sans-io wamp session
        self.session = session.WAMPSession(base_session.serializer)

        self._disconnect_callback: list[Callable[[], None] | None] = []

        thread = Thread(target=self.wait, daemon=False)
        thread.start()

    def wait(self):
        while self.base_session.transport.is_connected():
            try:
                data = self.base_session.receive()
            except Exception:
                break

            self.process_incoming_message(self.session.receive(data))

        for callback in self._disconnect_callback:
            callback()

    def process_incoming_message(self, msg: messages.Message):
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
                result = endpoint(types.Invocation(msg.args, msg.kwargs, msg.details))

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

                self.base_session.send(data)
            except ApplicationError as e:
                msg_to_send = messages.Error(messages.ErrorFields(msg.TYPE, msg.request_id, e.message, e.args))
                data = self.session.send_message(msg_to_send)
                self.base_session.send(data)
            except Exception as e:
                msg_to_send = messages.Error(
                    messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_RUNTIME_ERROR, [e.__str__()])
                )
                data = self.session.send_message(msg_to_send)
                self.base_session.send(data)
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
            try:
                endpoint = self.subscriptions[msg.subscription_id]
                endpoint(types.Event(msg.args, msg.kwargs, msg.details))
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

    def call(self, procedure: str, *args, **kwargs) -> types.Result:
        call_response = call(self.session, self.idgen, self.call_requests, procedure, *args, **kwargs)
        self.base_session.send(call_response.data)

        return call_response.future.result()

    def register(
        self,
        procedure: str,
        invocation_handler: Callable | Callable[[types.Invocation], types.Result],
        options: dict = None,
    ) -> types.Registration:
        register_response = register(
            self.session, self.idgen, self.register_requests, procedure, invocation_handler, options
        )
        self.base_session.send(register_response.data)

        return register_response.future.result()

    def unregister(self, reg: types.Registration):
        unregister = messages.Unregister(messages.UnregisterFields(self.idgen.next(), reg.registration_id))
        data = self.session.send_message(unregister)

        f: Future = Future()
        self.unregister_requests[unregister.request_id] = types.UnregisterRequest(f, reg.registration_id)
        self.base_session.send(data)

        f.result()

    def subscribe(
        self, topic: str, event_handler: Callable[[types.Event], None], options: dict = None
    ) -> types.Subscription:
        subscribe = messages.Subscribe(messages.SubscribeFields(self.idgen.next(), topic, options=options))
        data = self.session.send_message(subscribe)

        f: Future[types.Subscription] = Future()
        self.subscribe_requests[subscribe.request_id] = types.SubscribeRequest(f, event_handler)
        self.base_session.send(data)

        return f.result()

    def unsubscribe(self, sub: types.Subscription):
        unsubscribe = messages.Unsubscribe(messages.UnsubscribeFields(self.idgen.next(), sub.subscription_id))
        data = self.session.send_message(unsubscribe)

        f: Future = Future()
        self.unsubscribe_requests[unsubscribe.request_id] = types.UnsubscribeRequest(f, sub.subscription_id)
        self.base_session.send(data)

        f.result()

    def publish(self, topic: str, args: list[Any] = None, kwargs: dict = None, options: dict = None):
        publish = messages.Publish(messages.PublishFields(self.idgen.next(), topic, args, kwargs, options))
        data = self.session.send_message(publish)

        if options is not None and options.get("acknowledge", False):
            f: Future = Future()
            self.publish_requests[publish.request_id] = f
            self.base_session.send(data)
            return f.result()

        self.base_session.send(data)

    def leave(self):
        self.goodbye_request = Future()

        goodbye = messages.Goodbye(messages.GoodbyeFields({}, uris.CLOSE_REALM))
        data = self.session.send_message(goodbye)
        self.base_session.send(data)
        self.base_session.close()

        return self.goodbye_request.result(timeout=10)

    def ping(self, timeout: int = 10) -> float:
        return self.base_session.transport.ping(timeout)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        if callback is not None:
            self._disconnect_callback.append(callback)
