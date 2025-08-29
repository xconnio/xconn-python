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
(xconn-python) om26er@Home-PC:~$ xcorn sample:app --start-router
starting server on 127.0.0.1:8080
connected realm1
Registered procedure io.xconn.hello
Subscribed topic io.xconn.publish
```

# Client
This library provides two types of clients:
* `Client` for synchronous operations.
* `AsyncClient` for asynchronous operations.

## Sync Client
```python
from xconn.session import Session
from xconn.client import connect_anonymous

session: Session = connect_anonymous("ws://localhost:8080/ws", "realm1")
```
Once the session is established, you can perform WAMP actions. Below are examples of all four WAMP
operations:

### Subscribe to a topic
```python
from xconn.types import Event
from xconn.session import Session

def example_subscribe(session: Session):
    session.subscribe("io.xconn.example", event_handler)
    print("Subscribed to topic 'io.xconn.example'")


def event_handler(event: Event):
    print(f"Event Received: args={event.args}, kwargs={event.kwargs}, details={event.details}")
```

### Publish to a topic
```python
from xconn.session import Session

def example_publish(session: Session):
    session.publish("io.xconn.example", ["test"])
    print("Published to topic io.xconn.example")
```

### Register a procedure
```python
from xconn.session import Session
from xconn.types import Invocation

def example_register(session: Session):
    session.register("io.xconn.example", invocation_handler)


def invocation_handler(invocation: Invocation):
    print(f"Received args={invocation.args}, kwargs={invocation.kwargs}, details={invocation.details}")
```

### Call a procedure
```python
from xconn.session import Session

def example_call(session: Session):
    result = session.call("io.xconn.example", "1", "2", key="value")
    print(f"Received args={result.args}, kwargs={result.kwargs}, details={result.details}")
```

### Authentication
Authentication is straightforward.

#### Ticket Auth
```python
from xconn.session import Session
from xconn.client import connect_ticket

session: Session = connect_ticket("ws://localhost:8080/ws", "realm1", "authid", "ticket")
```

#### Challenge Response Auth
```python
from xconn.session import Session
from xconn.client import connect_wampcra

session: Session = connect_wampcra("ws://localhost:8080/ws", "realm1", "authid", "secret")
```

#### Cryptosign Auth
```python
from xconn.session import Session
from xconn.client import connect_cryptosign

session: Session = connect_cryptosign("ws://localhost:8080/ws", "realm1", "authid", "d850fff4ff199875c01d3e652e7205309dba2f053ae813c3d277609150adff13")
```

## Async Client
```python
from xconn import run
from xconn.async_session import AsyncSession
from xconn.async_client import connect_anonymous

async def main():
    session: AsyncSession = await connect_anonymous("ws://localhost:8080/ws", "realm1")

if __name__ == "__main__":
    run(main())
```
Once the session is established, you can perform WAMP actions. Below are examples of all 4 WAMP
operations:

### Subscribe to a topic
```python
from xconn.types import Event
from xconn.async_session import AsyncSession

async def example_subscribe(session: AsyncSession):
    await session.subscribe("io.xconn.example", event_handler)
    print("Subscribed to topic 'io.xconn.example'")


async def event_handler(event: Event):
    print(f"Event Received: args={event.args}, kwargs={event.kwargs}, details={event.details}")
```

### Publish to a topic
```python
from xconn.async_session import AsyncSession

async def example_publish(session: AsyncSession):
    await session.publish("io.xconn.example", ["test"])
    print("Published to topic io.xconn.example")
```

### Register a procedure
```python
from xconn.types import Invocation
from xconn.async_session import AsyncSession

async def example_register(session: AsyncSession):
    await session.register("io.xconn.example", invocation_handler)


async def invocation_handler(invocation: Invocation):
    print(f"Received args={invocation.args}, kwargs={invocation.kwargs}, details={invocation.details}")
```

### Call a procedure
```python
from xconn.async_session import AsyncSession

async def example_call(session: AsyncSession):
    result = await session.call("io.xconn.example", "1", "2", key="value")
    print(f"Received args={result.args}, kwargs={result.kwargs}, details={result.details}")
```

### Authentication
Authentication is straightforward.

#### Ticket Auth
```python
from xconn import run
from xconn.async_session import AsyncSession
from xconn.async_client import connect_ticket

async def connect():
    session: AsyncSession = await connect_ticket("ws://localhost:8080/ws", "realm1", "authid", "ticket")

if __name__ == "__main__":
    run(connect())
```

#### Challenge Response Auth
```python
from xconn import run
from xconn.async_session import AsyncSession
from xconn.async_client import connect_wampcra

async def connect():
    session: AsyncSession = await connect_wampcra("ws://localhost:8080/ws", "realm1", "authid", "secret")

if __name__ == "__main__":
    run(connect())
```

#### Cryptosign Auth
```python
from xconn import run
from xconn.async_session import AsyncSession
from xconn.async_client import connect_cryptosign

async def connect():
    session: AsyncSession = await connect_cryptosign("ws://localhost:8080/ws", "realm1", "authid", "d850fff4ff199875c01d3e652e7205309dba2f053ae813c3d277609150adff13")

if __name__ == "__main__":
    run(connect())
```

look at examples directory for more [examples](examples)
