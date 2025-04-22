from pydantic import BaseModel

from xconn import App, Component, register, subscribe
from xconn.types import Result, Event, Invocation


comp = Component()


class Data(BaseModel):
    name: str


class ReturnData(BaseModel):
    name: str


@comp.register("io.xconn.component.echo", response_model=ReturnData)
async def included_echo(data: Data) -> Result:
    return Result(args=[data.name])


@comp.subscribe("io.xconn.component.yo")
def included_event(event: Event) -> None:
    print(app.session)
    print(event.args)


class Test(Component):
    @register("hello")
    async def hello(self, name: str):
        print("CALLED", name)

    @subscribe("topic")
    def topic(self, event):
        print("TOPIC", event)


class_component = Test()

app = App()
app.include_component(comp)
app.include_component(class_component)


@app.register("io.xconn.echo")
async def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
def login(event: Event) -> None:
    print(app.session)
    print(event.args)
