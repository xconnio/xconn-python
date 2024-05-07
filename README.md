# XConn
Real-time application development framework for Python. XConn enables backend APIs that are FAST, support PubSub and
are secure.

# Getting started
Install xconn from pypi
```shell
uv venv
uv pip install xconn
./.venv/bin/xconn
```
writing your first API is quick

```python
from xconn import XConnApp
from xconn.types import Invocation, Result

app = XConnApp()


@app.register("io.xconn.echo")
def echo(invocation: Invocation) -> Result:
    return Result(args=invocation.args, kwargs=invocation.kwargs)
```
run the app with xconn command line
```shell
om26er@office-pc-1:~/$ ./.venv/bin/xconn main:app
registered procedure io.xconn.echo
Listening for websocket connections on ws://127.0.0.1:8080/ws
```
look at examples directory for more [examples](examples)
