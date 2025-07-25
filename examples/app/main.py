from xconn import App, Component, register, subscribe
from xconn.app import ExecutionMode
from xconn.types import (
    Result,
    Event,
    Invocation,
    Depends,
    RegisterOptions,
    InvokeOptions,
    SubscribeOptions,
    MatchOptions,
)

from models import InData, OutData, UserProfile, Address, ContactInfo


functional_component = Component()


async def get_database() -> str:
    return "HELLO"


async def get_more():
    try:
        yield "MORE"
    finally:
        print("END")


@functional_component.register("io.xconn.component.echo", response_model=OutData)
async def included_echo(data: InData) -> tuple[str, str, int]:
    return data.first_name, data.last_name, data.age


@functional_component.subscribe("io.xconn.component.yo", options=SubscribeOptions(match=MatchOptions.PREFIX))
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
app.set_execution_mode(ExecutionMode.ASYNC)
app.include_component(functional_component)
app.include_component(class_component)


async def on_startup():
    print("app started...")


app.add_event_handler("startup", on_startup)
app.set_schema_procedure("io.xconn.schema.get")


@app.register("io.xconn.echo")
async def echo(inv: Invocation) -> Result:
    return Result(args=inv.args, kwargs=inv.kwargs)


@app.subscribe("io.xconn.yo")
async def login(name: str, city: str) -> None:
    print(app.session)
    print(name, city)


@app.register("io.xconn.dynamic")
async def dynamic(name: str, city: str, age: int, address: str = None) -> tuple:
    return name, city, age, address


@app.register("io.xconn.not_allowed", allowed_roles=["test"])
async def not_allowed() -> None:
    pass


@app.register("io.xconn.depends")
async def depends(data: InData, db: str = Depends(get_database), test: str = Depends(get_more)) -> None:
    print(data, db, test)


@app.register("io.xconn.roundrobin", options=RegisterOptions(invoke=InvokeOptions.ROUNDROBIN))
async def roundrobin_one():
    print("roundrobin_one")


@app.register("io.xconn.user.profile.get", response_model=UserProfile)
async def profile(data: UserProfile) -> tuple[str, int, Address, ContactInfo]:
    return data.name, data.age, data.address, data.contact
