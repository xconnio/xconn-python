import sys
import signal

from xconn import Client
from xconn.types import Result


def sum_handler(*args, **kwargs) -> Result:
    print(f"Received args={args}, kwargs={kwargs}")
    total_sum = 0
    for arg in args:
        total_sum += arg

    return Result(args=[total_sum])


if __name__ == "__main__":
    test_procedure_sum = "io.xconn.sum"
    test_procedure_echo = "io.xconn.echo"
    test_procedure_no_result = "io.xconn.result"

    # create and connect a callee client to server
    client = Client()
    callee = client.connect("ws://localhost:8080/ws", "realm1")

    # function to handle received Invocation for "io.xconn.echo"
    def echo(*args, **kwargs) -> Result:
        print(f"Received args={args}, kwargs={kwargs}")
        return Result(args, kwargs)

    # function to handle received Invocation for "io.xconn.result"
    def no_result_handler(*args, **kwargs):
        print(f"Received args={args}, kwargs={kwargs}")

    echo_registration = callee.register(test_procedure_echo, echo)
    print(f"Registered procedure '{test_procedure_echo}'")

    no_result_registration = callee.register(test_procedure_no_result, no_result_handler)
    print(f"Registered procedure '{test_procedure_no_result}'")

    sum_registration = callee.register(test_procedure_sum, sum_handler)
    print(f"Registered procedure '{test_procedure_sum}'")

    def handle_sigint(signum, frame):
        print("SIGINT received. Cleaning up...")

        # unregister procedure "io.xconn.echo"
        callee.unregister(echo_registration)

        # unregister procedure "io.xconn.result"
        callee.unregister(no_result_registration)

        # unregister procedure "io.xconn.sum"
        callee.unregister(sum_registration)

        # close connection to the server
        callee.leave()

        sys.exit(0)


# register signal handler
signal.signal(signal.SIGINT, handle_sigint)
