from datetime import date
import time

from xconn.app import WampApp
from xconn.types import Invocation, Result

app = WampApp()


@app.register("io.xconn.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)


@app.register("io.xconn.date.get")
def get_date(_: Invocation) -> Result:
    return Result(args=[date.today().isoformat()])


@app.register("io.xconn.uptime.get")
def get_uptime(_: Invocation) -> Result:
    return Result(args=[time.clock_gettime(time.CLOCK_BOOTTIME)])
