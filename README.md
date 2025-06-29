# XConn
Real-time application development framework for Python. XConn enables backend APIs that are FAST, support PubSub and
are secure.

# Getting started
Install xconn from pypi
```shell
om26er@Home-PC:~$ uv venv
om26er@Home-PC:~$ uv pip install git+ssh://git@github.com/xconnio/xconn-python.git
om26er@Home-PC:~$ source .venv/bin/activate
(xconn-python) om26er@Home-PC:~$
```

Save the below code in sample.py
```python
from xconn import App

app = App()

@app.register("io.xconn.hello")
async def my_procedure(first_name: str, last_name: str, age: int):
    print(first_name + " " + last_name + " " + str(age))
    return first_name, last_name, age


@app.subscribe("io.xconn.publish")
async def my_topic():
    print("received event...")
```
run the app with xcorn command (note: this automatically starts the debug router)
```shell
(xconn-python) om26er@Home-PC:~$ xcorn sample:app --asyncio --start-router
starting server on 127.0.0.1:8080
connected realm1
Registered procedure io.xconn.hello
Subscribed topic io.xconn.publish
```
look at examples directory for more [examples](examples)
