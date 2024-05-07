from xconn import XConnApp
from xconn.types import Invocation, Result

app = XConnApp()


@app.register("foo.bar.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)
