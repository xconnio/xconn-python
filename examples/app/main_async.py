from xconn import App, Component, register, subscribe
from xconn.types import Result, Event, Invocation, Depends

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
    async def hello(self):
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


async def on_startup():
    print("app started...")


app.add_event_handler("startup", on_startup)


@app.register("io.xconn.echo")
async def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
async def login(event: Event) -> None:
    print(app.session)
    print(event.args)


@app.register("io.xconn.dynamic")
async def dynamic(name: str, city: str, age: int, address: str = None) -> tuple:
    return name, city, age, address


@app.register("io.xconn.not_allowed", allowed_roles=["test"])
async def not_allowed() -> None:
    pass


async def get_database() -> str:
    return "HELLO"


async def get_more():
    try:
        yield "MORE"
    finally:
        print("END")


@app.register("io.xconn.depends")
async def depends(db: str = Depends(get_database), test: str = Depends(get_more)) -> None:
    print(db, test)
