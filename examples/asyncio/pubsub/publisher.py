from xconn import AsyncClient, run


async def main() -> None:
    test_topic = "io.xconn.test"

    # create and connect a publisher client to server
    client = AsyncClient()
    publisher = await client.connect("ws://localhost:8080/ws", "realm1")

    # publish event to topic
    await publisher.publish(test_topic)

    # publish event with args
    await publisher.publish(test_topic, args=["Hello", "World"])

    # publish event with kwargs
    await publisher.publish(test_topic, kwargs={"Hello World!": "I love WAMP"})

    # publish event with options
    await publisher.publish(test_topic, options={"acknowledge": True})

    # publish event with args and kwargs
    await publisher.publish(test_topic, args=["Hello", "World!"], kwargs={"Hello World!": "I love WAMP"})

    # publish event with args, kwargs and options
    await publisher.publish(
        test_topic, args=["Hello", "World!"], kwargs={"Hello World!": "I love WAMP"}, options={"acknowledge": True}
    )

    print(f"Published events to {test_topic}")

    # leave the server
    await publisher.leave()


if __name__ == "__main__":
    run(main())
