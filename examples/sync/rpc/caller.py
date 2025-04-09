from xconn import Client

if __name__ == "__main__":
    test_procedure_sum = "io.xconn.sum"
    test_procedure_echo = "io.xconn.echo"

    # create and connect a caller client to server
    client = Client()
    caller = client.connect("ws://localhost:8080/ws", "realm1")

    # call procedure "io.xconn.echo"
    result = caller.call(test_procedure_echo, "hello", "world", key="value")
    print(f"Result of procedure '{test_procedure_echo}': args={result.args}, kwargs={result.kwargs}")

    # call procedure "io.xconn.result" with args
    caller.call(test_procedure_echo, "hello", "world")

    # call procedure "io.xconn.result" with kwargs
    caller.call(test_procedure_echo, name="john")

    # call procedure "io.xconn.result" with args & kwargs
    caller.call(test_procedure_echo, 1, 2, name="john")

    sum_result = caller.call(test_procedure_sum, 2, 2, 6)
    print(f"Sum={sum_result.args[0]}")

    # close connection to the server
    caller.leave()
