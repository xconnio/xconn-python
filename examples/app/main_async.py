from xconn import App, Component, register, subscribe
from xconn.types import Result, Event, Invocation

from models import InData, OutData


functional_component = Component()


@functional_component.register("io.xconn.component.echo", response_model=OutData)
async def included_echo(data: InData) -> tuple[str, str, int]:
    return data.first_name, data.last_name, data.age


@functional_component.subscribe("io.xconn.component.yo")
async def included_event(data: InData) -> None:
    print(data)


class Test(Component):
    @register("hello", response_model=OutData)
    async def hello(self, inv: Invocation):
        return (
            "john",
            "wick",
            40,
        )

    @subscribe("topic")
    async def topic(self, event: Event) -> None:
        print("TOPIC", event)


class_component = Test()

app = App()
app.include_component(functional_component)
app.include_component(class_component)


@app.register("io.xconn.echo")
async def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
async def login(event: Event) -> None:
    print(app.session)
    print(event.args)
