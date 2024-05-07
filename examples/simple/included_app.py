from xconn.app import WampApp
from xconn.types import Invocation, Result

app = WampApp()


@app.register("foo.bar.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)
