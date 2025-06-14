from typing import Any, Generator

from xconn import App, Component, register, subscribe
from xconn.types import Result, Event, Invocation, Depends, CallDetails

from models import InData, OutData


functional_component = Component()


@functional_component.register("io.xconn.component.echo", response_model=OutData)
def included_echo(data: InData) -> tuple[str, str, int]:
    return data.first_name, data.last_name, data.age


@functional_component.subscribe("io.xconn.component.yo")
def included_event(data: InData) -> None:
    print(data)


class Test(Component):
    @register("hello", response_model=OutData)
    def hello(self, inv: Invocation):
        return (
            "john",
            "wick",
            40,
        )

    @subscribe("topic")
    def topic(self, event: Event) -> None:
        print("TOPIC", event)


class_component = Test()

app = App()
app.include_component(functional_component)
app.include_component(class_component)


def on_startup():
    print("app started...")


app.add_event_handler("startup", on_startup)


@app.register("io.xconn.echo")
def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
def login(name: str, city: str) -> None:
    print(app.session)
    print(name, city)


@app.register("io.xconn.not_allowed", allowed_roles=["test"])
def dynamic() -> None:
    pass


def get_database() -> str:
    return "HELLO"


def get_more() -> Generator[str, Any, None]:
    try:
        yield "MORE"
    finally:
        print("END")


@app.register("io.xconn.depends")
def not_allowed(details: CallDetails, db: str = Depends(get_database), test: str = Depends(get_more)) -> None:
    print(details, db, test)
