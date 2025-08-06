from xconn import AsyncClient, run
from xconn.types import Result, Invocation


async def sum_handler(inv: Invocation) -> Result:
    print(f"Received args={inv.args}, kwargs={inv.kwargs}")
    total_sum = 0
    for arg in inv.args:
        total_sum += arg

    return Result(args=[total_sum])


async def main() -> None:
    test_procedure_sum = "io.xconn.sum"
    test_procedure_echo = "io.xconn.echo"
    test_procedure_no_result = "io.xconn.result"
    test_procedure_async_echo = "io.xconn.async.echo"

    # create and connect a callee client to server
    client = AsyncClient()
    callee = await client.connect("ws://localhost:8080/ws", "realm1")

    # function to handle received Invocation for "io.xconn.echo"
    async def echo(inv: Invocation) -> Result:
        print(f"Received args={inv.args}, kwargs={inv.kwargs}")
        return Result(inv.args, inv.kwargs)

    # function to handle received Invocation for "io.xconn.async.echo"
    async def async_echo(inv: Invocation) -> Result:
        print(f"Received args={inv.args}, kwargs={inv.kwargs}")
        return Result(inv.args, inv.kwargs)

    # function to handle received Invocation for "io.xconn.result"
    async def no_result_handler(inv: Invocation):
        print(f"Received args={inv.args}, kwargs={inv.kwargs}")

    await callee.register(test_procedure_echo, echo)
    print(f"Registered procedure '{test_procedure_echo}'")

    await callee.register(test_procedure_async_echo, async_echo)
    print(f"Registered procedure '{test_procedure_async_echo}'")

    await callee.register(test_procedure_no_result, no_result_handler)
    print(f"Registered procedure '{test_procedure_no_result}'")

    await callee.register(test_procedure_sum, sum_handler)
    print(f"Registered procedure '{test_procedure_sum}'")


if __name__ == "__main__":
    run(main())
