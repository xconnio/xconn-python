import asyncio
from typing import Callable, Type, Awaitable
import inspect

from pydantic import BaseModel

from xconn.client import Session, AsyncSession


class IComponent:
    def set_session(self, session: Session | AsyncSession):
        raise NotImplementedError()

    @property
    def session(self) -> Session | AsyncSession:
        raise NotImplementedError()

    @property
    def procedures(self) -> dict[str, Callable]:
        raise NotImplementedError()

    @property
    def topics(self) -> dict[str, Callable]:
        raise NotImplementedError()

    def register(self, procedure: str):
        raise NotImplementedError()

    def subscribe(self, topic: str):
        raise NotImplementedError()


def register(
    procedure: str,
    response_model: Type[BaseModel] | None = None,
):
    def _register(func):
        func.__xconn_procedure__ = procedure
        func.__xconn_response_model__ = response_model
        return func

    return _register


def subscribe(topic: str):
    def _subscribe(func):
        func.__xconn_topic__ = topic
        return func

    return _subscribe


class Component(IComponent):
    def __init__(self):
        super().__init__()
        self._procedures = {}
        self._topics = {}

        self._session: Session | AsyncSession = None

        for name, method in inspect.getmembers(self.__class__, inspect.isfunction):
            if getattr(method, "__xconn_procedure__", False):
                self._procedures[name] = method.__get__(self)
            elif getattr(method, "__xconn_topic__", False):
                self._topics[name] = method.__get__(self)

    def set_session(self, session: Session | AsyncSession):
        self._session = session

    @property
    def session(self) -> Session | AsyncSession:
        return self._session

    @property
    def procedures(self) -> dict[str, Callable]:
        return self._procedures

    @property
    def topics(self) -> dict[str, Callable]:
        return self._topics

    def register(self, procedure: str, response_model: Type[BaseModel] | None = None):
        def _register(func):
            if procedure in self._procedures:
                raise ValueError(f"procedure {procedure} already registered")

            if response_model is not None:
                if not issubclass(response_model, BaseModel):
                    raise ValueError(f"response_model {response_model} is not a subclass of BaseModel")

            func.__xconn_response_model__ = response_model
            self._procedures[procedure] = func

        return _register

    def subscribe(self, topic: str):
        def _subscribe(func):
            if topic in self._topics:
                raise ValueError(f"topic {topic} already registered")

            self._topics[topic] = func

        return _subscribe


class App(Component):
    def __init__(self):
        super().__init__()
        self._procedures = {}
        self._topics = {}

        self._session: Session | AsyncSession = None
        self._components: list[Component] = []

        self._startup_handler: Callable | Awaitable[None] = None

    def set_session(self, session: Session | AsyncSession):
        self._session = session
        for component in self._components:
            component.set_session(session)

        if self._startup_handler is not None:
            if inspect.iscoroutinefunction(self._startup_handler):
                asyncio.create_task(self._startup_handler())
            else:
                self._startup_handler()

    @property
    def components(self) -> list[Component]:
        return self._components

    def include_component(self, component: Component, prefix: str = "") -> None:
        if prefix is None or len(prefix) == 0:
            self._procedures.update(component.procedures)
            self._topics.update(component.topics)
        else:
            for procedure, func in component.procedures.items():
                self._procedures.update({prefix + procedure: func})

            for topic, func in component.topics.items():
                self._topics.update({prefix + topic: func})

        self._components.append(component)

    def add_event_handler(self, event_type: str, handler: Callable | Awaitable):
        if event_type != "startup":
            raise ValueError(f"event_type {event_type} is not supported")

        self._startup_handler = handler
