from wamp.app import WampApp
from wamp.types import Invocation, Result

app = WampApp()


@app.register("foo.bar")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)
