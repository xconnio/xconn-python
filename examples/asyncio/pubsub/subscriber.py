from xconn import AsyncClient, run
from xconn.types import Event


async def main() -> None:
    test_topic = "io.xconn.test"

    # create and connect a subscriber client to server
    client = AsyncClient()
    subscriber = await client.connect("ws://localhost:8080/ws", "realm1")

    def event_handler(event: Event):
        print(f"Received Event: args={event.args}, kwargs={event.kwargs}, details={event.details}")

    await subscriber.subscribe(test_topic, event_handler)
    print(f"Subscribed to topic: {test_topic}")


if __name__ == "__main__":
    run(main())
