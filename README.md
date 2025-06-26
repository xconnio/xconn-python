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
Initialize the app
```shell
(xconn-python) om26er@Home-PC:~$ xapp init
XConn App initialized.
The config is xapp.yaml and sample app is sample.py. Run below command to start the sample

xapp start sample:app --asyncio --start-router
```
The sample file looks like below
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
run the app with xapp command line (note: this automatically starts the debug router)
```shell
(xconn-python) om26er@Home-PC:~$ xapp start sample:app --asyncio --start-router
starting server on 127.0.0.1:8080
connected realm1
Registered procedure io.xconn.hello
Subscribed topic io.xconn.publish
```
look at examples directory for more [examples](examples)
