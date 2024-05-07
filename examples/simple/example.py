from datetime import date
import time

from xconn import XConnApp
from xconn.types import Invocation, Result

from included_app import app as included_app

app = XConnApp()
app.include_app(included_app, prefix="test.")


@app.register("io.xconn.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)


@app.register("io.xconn.date.get")
def get_date(_: Invocation) -> Result:
    return Result(args=[date.today().isoformat()])


@app.register("io.xconn.uptime.get")
def get_uptime(_: Invocation) -> Result:
    return Result(args=[time.clock_gettime(time.CLOCK_BOOTTIME)])
