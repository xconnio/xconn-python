from xconn import run
from xconn.types import Result
from xconn.async_client import connect_anonymous


async def progress_handler(res: Result) -> None:
    progress = res.args[0]
    print(f"Download progress: {progress}%")


async def main() -> None:
    test_procedure_progress_download = "io.xconn.progress.download"

    # create and connect a callee client to server
    caller = await connect_anonymous("ws://localhost:8080/ws", "realm1")

    await caller.call_progress(test_procedure_progress_download, progress_handler)


if __name__ == "__main__":
    run(main())
