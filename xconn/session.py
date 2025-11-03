from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, wait
import threading
from os import cpu_count
from typing import Callable, Any
from dataclasses import dataclass

from wampproto import messages, session, uris

from xconn import types, exception, uris as xconn_uris
from xconn.exception import ApplicationError
from xconn.helpers import exception_from_error, SessionScopeIDGenerator


@dataclass
class RegisterRequest:
    future: Future[Registration]
    endpoint: Callable | Callable[[types.Invocation], types.Result]


class Registration:
    def __init__(self, registration_id: int, session: Session):
        self.registration_id = registration_id
        self._session = session

    def unregister(self) -> None:
        self._session._unregister(self)


@dataclass
class SubscribeRequest:
    future: Future[Subscription]
    endpoint: Callable[[types.Event], None]


class Subscription:
    def __init__(self, subscription_id: int, session: Session):
        self.subscription_id = subscription_id
        self._session = session

    def unsubscribe(self) -> None:
        self._session._unsubscribe(self)


class Session:
    def __init__(self, base_session: types.BaseSession):
        # RPC data structures
        self._call_requests: dict[int, Future[types.Result]] = {}
        self._register_requests: dict[int, RegisterRequest] = {}
        self._registrations: dict[int, Callable[[types.Invocation], types.Result]] = {}
        self._unregister_requests: dict[int, types.UnregisterRequest] = {}

        # PubSub data structures
        self._publish_requests: dict[int, Future[None]] = {}
        self._subscribe_requests: dict[int, SubscribeRequest] = {}
        self._subscriptions: dict[int, Callable[[types.Event], None]] = {}
        self._unsubscribe_requests: dict[int, types.UnsubscribeRequest] = {}

        self._goodbye_request = Future()

        # ID generator
        self._idgen = SessionScopeIDGenerator()

        self._base_session = base_session

        # initialize the sans-io wamp session
        self._session = session.WAMPSession(base_session.serializer)

        self._disconnect_callback: list[Callable[[], None] | None] = []
        self._stopped = threading.Event()

        # callback executor thread-pool
        self._executor = ThreadPoolExecutor(max_workers=cpu_count() or 4)

        thread = threading.Thread(target=self._wait, daemon=True)
        thread.start()

    def _wait(self):
        while self._base_session.transport.is_connected():
            try:
                data = self._base_session.receive()
            except Exception:
                break

            self._process_incoming_message(self._session.receive(data))

        # Shut down executor, cancelling anything still running
        self._executor.shutdown(cancel_futures=True, wait=False)

        if self._disconnect_callback:
            with ThreadPoolExecutor(max_workers=len(self._disconnect_callback)) as executor:
                # Trigger disconnect callbacks concurrently
                futures = [executor.submit(cb) for cb in self._disconnect_callback]
                # Wait up to 1 second for them to finish
                wait(futures, timeout=1)

        self._stopped.set()

    def _handle_invocation(self, msg: messages.Invocation, endpoint: Callable[[types.Invocation], types.Result]):
        try:
            result = endpoint(types.Invocation(msg.args, msg.kwargs, msg.details))

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

            self._base_session.send(data)
        except ApplicationError as e:
            msg_to_send = messages.Error(messages.ErrorFields(msg.TYPE, msg.request_id, e.message, e.args))
            data = self._session.send_message(msg_to_send)
            self._base_session.send(data)
        except Exception as e:
            msg_to_send = messages.Error(
                messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_RUNTIME_ERROR, [e.__str__()])
            )
            data = self._session.send_message(msg_to_send)
            self._base_session.send(data)

    def _handle_event(self, msg: messages.Event, endpoint: Callable[[types.Event], None]):
        try:
            endpoint(types.Event(msg.args, msg.kwargs, msg.details))
        except Exception as e:
            print(e)

    def _process_incoming_message(self, msg: messages.Message):
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
                self._executor.submit(self._handle_invocation, msg, endpoint)
            except Exception as e:
                msg_to_send = messages.Error(
                    messages.ErrorFields(msg.TYPE, msg.request_id, xconn_uris.ERROR_RUNTIME_ERROR, [e.__str__()])
                )
                data = self._session.send_message(msg_to_send)
                self._base_session.send(data)
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
            try:
                endpoint = self._subscriptions[msg.subscription_id]
                self._executor.submit(self._handle_event, msg, endpoint)
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

    def call(
        self,
        procedure: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> types.Result:
        if options is not None and options.get("x_payload_raw", False):
            options.pop("x_payload_raw", None)
            if len(args) > 1:
                raise TypeError("must provide at most one argument when 'x_payload_raw' is set")

            if len(kwargs) != 0:
                raise TypeError("must not provide kwargs when 'x_payload_raw' is set")

            if len(args) == 0:
                call = messages.Call(
                    messages.CallFields(self._idgen.next(), procedure, options=options, serializer=0, binary=True)
                )
            else:
                if not isinstance(args[0], bytearray):
                    raise TypeError("argument must be of type bytearray when 'x_payload_raw' is set")

                call = messages.Call(
                    messages.CallFields(
                        self._idgen.next(),
                        procedure,
                        options=options,
                        payload=args[0],
                        serializer=0,
                        binary=True,
                    )
                )
        else:
            call = messages.Call(messages.CallFields(self._idgen.next(), procedure, args, kwargs, options=options))

        data = self._session.send_message(call)

        f = Future()
        self._call_requests[call.request_id] = f
        self._base_session.send(data)

        return f.result()

    def register(
        self,
        procedure: str,
        invocation_handler: Callable | Callable[[types.Invocation], types.Result],
        options: dict = None,
    ) -> Registration:
        register = messages.Register(messages.RegisterFields(self._idgen.next(), procedure, options=options))
        data = self._session.send_message(register)

        f: Future[Registration] = Future()
        self._register_requests[register.request_id] = RegisterRequest(f, invocation_handler)

        self._base_session.send(data)

        return f.result()

    def _unregister(self, reg: Registration) -> None:
        if not self._base_session.transport.is_connected():
            raise Exception("cannot unregister procedure: session not established")

        unregister = messages.Unregister(messages.UnregisterFields(self._idgen.next(), reg.registration_id))
        data = self._session.send_message(unregister)

        f: Future = Future()
        self._unregister_requests[unregister.request_id] = types.UnregisterRequest(f, reg.registration_id)
        self._base_session.send(data)

        f.result()

    def subscribe(self, topic: str, event_handler: Callable[[types.Event], None], options: dict = None) -> Subscription:
        subscribe = messages.Subscribe(messages.SubscribeFields(self._idgen.next(), topic, options=options))
        data = self._session.send_message(subscribe)

        f: Future[Subscription] = Future()
        self._subscribe_requests[subscribe.request_id] = SubscribeRequest(f, event_handler)
        self._base_session.send(data)

        return f.result()

    def publish(self, topic: str, args: list[Any] = None, kwargs: dict = None, options: dict = None):
        publish = messages.Publish(messages.PublishFields(self._idgen.next(), topic, args, kwargs, options))
        data = self._session.send_message(publish)

        if options is not None and options.get("acknowledge", False):
            f: Future = Future()
            self._publish_requests[publish.request_id] = f
            self._base_session.send(data)
            return f.result()

        self._base_session.send(data)

    def _unsubscribe(self, sub: Subscription) -> None:
        if not self._base_session.transport.is_connected():
            raise Exception("cannot unsubscribe topic: session not established")

        unsubscribe = messages.Unsubscribe(messages.UnsubscribeFields(self._idgen.next(), sub.subscription_id))
        data = self._session.send_message(unsubscribe)

        f: Future = Future()
        self._unsubscribe_requests[unsubscribe.request_id] = types.UnsubscribeRequest(f, sub.subscription_id)
        self._base_session.send(data)

        f.result()

    def leave(self):
        self._goodbye_request = Future()

        goodbye = messages.Goodbye(messages.GoodbyeFields({}, uris.CLOSE_REALM))
        data = self._session.send_message(goodbye)
        self._base_session.send(data)
        try:
            self._goodbye_request.result(timeout=10)
        finally:
            self._base_session.close()

    def ping(self, timeout: int = 10) -> float:
        return self._base_session.transport.ping(timeout)

    def _on_disconnect(self, callback: Callable[[], None]) -> None:
        if callback is not None:
            self._disconnect_callback.append(callback)

    def run_forever(self):
        """Block until the session is closed/disconnected."""
        print("[Session] Running forever — press Ctrl+C to exit.")
        try:
            self._stopped.wait()
        except KeyboardInterrupt:
            print("[Session] Interrupted — shutting down...")
            self.leave()
