from xconn import Component
from xconn.types import Invocation, Result

component = Component()


@component.register("foo.bar.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)
