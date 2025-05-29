from pydantic import BaseModel

from xconn import App, Component, register, subscribe
from xconn.types import Result, Event, Invocation


comp = Component()


class InData(BaseModel):
    name: str


class OutData(BaseModel):
    name: str
    city: str

    model_config = {"from_attributes": True}


class MyData:
    def __init__(self):
        super().__init__()
        self.name = "my name"


@comp.register("io.xconn.component.echo", response_model=OutData)
def included_echo(data: InData) -> tuple[str, str]:
    return "hello", "ok"


@comp.subscribe("io.xconn.component.yo")
def included_event(event: Event) -> None:
    print(app.session)
    print(event.args)


class Test(Component):
    @register("hello", response_model=OutData)
    def hello(self, name: str):
        return ("hello", "ok", 1, None), {"name": 1}

    @subscribe("topic")
    def topic(self, event: str):
        print("TOPIC", event)


class_component = Test()

app = App()
app.include_component(comp)
app.include_component(class_component)


@app.register("io.xconn.echo")
def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
def login(event: Event) -> None:
    print(app.session)
    print(event.args)
