from xconn import Client

if __name__ == "__main__":
    test_topic = "io.xconn.test"

    # create and connect a publisher client to server
    client = Client()
    publisher = client.connect("ws://localhost:8080/ws", "realm1")

    # publish event to topic
    publisher.publish(test_topic)

    # publish event with args
    publisher.publish(test_topic, args=["Hello", "World"])

    # publish event with kwargs
    publisher.publish(test_topic, kwargs={"Hello World!": "I love WAMP"})

    # publish event with options
    publisher.publish(test_topic, options={"acknowledge": True})

    # publish event with args and kwargs
    publisher.publish(test_topic, args=["Hello", "World!"], kwargs={"Hello World!": "I love WAMP"})

    # publish event with args, kwargs and options
    publisher.publish(
        test_topic, args=["Hello", "World!"], kwargs={"Hello World!": "I love WAMP"}, options={"acknowledge": True}
    )

    print(f"Published events to {test_topic}")

    # leave the server
    publisher.leave()
