import sys
import time
import signal

from xconn.client import connect_anonymous
from xconn.types import Result, Invocation


def invocation_handler(invocation: Invocation) -> Result:
    file_size = 100
    for i in range(0, file_size + 1, 10):
        progress = i * 100 // file_size
        try:
            invocation.send_progress([progress], {})
        except Exception as err:
            return Result(["wamp.error.canceled", str(err)])
        time.sleep(0.5)

    return Result(["Download complete!"])


if __name__ == "__main__":
    test_procedure_progress_download = "io.xconn.progress.download"

    # create and connect a callee client to server
    callee = connect_anonymous("ws://localhost:8080/ws", "realm1")

    download_progress_registration = callee.register(test_procedure_progress_download, invocation_handler)
    print(f"Registered procedure '{test_procedure_progress_download}'")

    def handle_sigint(signum, frame):
        print("SIGINT received. Cleaning up...")

        # unregister procedure "io.xconn.progress.download"
        download_progress_registration.unregister()

        # close connection to the server
        callee.leave()

        sys.exit(0)


# register signal handler
signal.signal(signal.SIGINT, handle_sigint)
