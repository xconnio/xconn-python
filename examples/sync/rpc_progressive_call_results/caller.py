from xconn.types import Result
from xconn.client import connect_anonymous


def progress_handler(res: Result) -> None:
    progress = res.args[0]
    print(f"Download progress: {progress}%")


if __name__ == "__main__":
    test_procedure_progress_download = "io.xconn.progress.download"

    # create and connect a callee client to server
    caller = connect_anonymous("ws://localhost:8080/ws", "realm1")

    caller.call_progress(test_procedure_progress_download, progress_handler)

    caller.leave()
