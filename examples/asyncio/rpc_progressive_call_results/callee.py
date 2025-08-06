import asyncio

from xconn import run
from xconn.types import Result, Invocation
from xconn.async_client import connect_anonymous


async def invocation_handler(invocation: Invocation) -> Result:
    file_size = 100
    for i in range(0, file_size + 1, 10):
        progress = i * 100 // file_size
        try:
            await invocation.send_progress([progress], {})
        except Exception as err:
            return Result(["wamp.error.canceled", str(err)])
        await asyncio.sleep(0.5)

    return Result(["Download complete!"])


async def main() -> None:
    test_procedure_progress_download = "io.xconn.progress.download"

    # create and connect a callee client to server
    callee = await connect_anonymous("ws://localhost:8080/ws", "realm1")

    await callee.register(test_procedure_progress_download, invocation_handler)
    print(f"Registered procedure '{test_procedure_progress_download}'")


if __name__ == "__main__":
    run(main())
