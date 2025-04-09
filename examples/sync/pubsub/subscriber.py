import sys
import signal

from xconn import Client
from xconn.types import Event


if __name__ == "__main__":
    test_topic = "io.xconn.test"

    # create and connect a subscriber client to server
    client = Client()
    subscriber = client.connect("ws://localhost:8080/ws", "realm1")

    def event_handler(event: Event):
        print(f"Received Event: args={event.args}, kwargs={event.kwargs}, details={event.details}")

    subscription = subscriber.subscribe(test_topic, event_handler)
    print(f"Subscribed to topic: {test_topic}")


def handle_sigint(signum, frame):
    print("SIGINT received. Cleaning up...")

    # unsubscribe from topic
    subscriber.unsubscribe(subscription)

    # close connection to the server
    subscriber.leave()

    sys.exit(0)


# register signal handler
signal.signal(signal.SIGINT, handle_sigint)
