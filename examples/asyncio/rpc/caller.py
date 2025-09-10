from xconn import AsyncClient, run


async def main() -> None:
    test_procedure_sum = "io.xconn.sum"
    test_procedure_echo = "io.xconn.echo"
    test_procedure_async_echo = "io.xconn.async.echo"

    # create and connect a caller client to server
    client = AsyncClient()
    caller = await client.connect("ws://localhost:8080/ws", "realm1")

    # call procedure "io.xconn.echo"
    result = await caller.call(test_procedure_echo, ["hello", "world"], {"key": "value"})
    print(f"Result of procedure '{test_procedure_echo}': args={result.args}, kwargs={result.kwargs}")

    # call procedure "io.xconn.echo"
    result = await caller.call(test_procedure_async_echo, ["hello", "world", "async"], {"key": "value"})
    print(f"Result of procedure '{test_procedure_async_echo}': args={result.args}, kwargs={result.kwargs}")

    # call procedure "io.xconn.result" with args
    await caller.call(test_procedure_echo, ["hello", "world"])

    # call procedure "io.xconn.result" with kwargs
    await caller.call(test_procedure_echo, kwargs={"name": "john"})

    # call procedure "io.xconn.result" with args & kwargs
    await caller.call(test_procedure_echo, [1, 2], kwargs={"name":"john"})

    sum_result = await caller.call(test_procedure_sum, [2, 2, 6])
    print(f"Sum={sum_result.args[0]}")

    # close connection to the server
    await caller.leave()


if __name__ == "__main__":
    run(main())
