from threading import Thread
import socket

from wampproto import types

from wamp import wsacceptor, wsjoiner


def accept(sock: socket.socket, result: [types.SessionDetails]):
    conn, _ = sock.accept()
    a = wsacceptor.WAMPSessionAcceptor()
    details = a.accept(conn)
    conn.close()

    result.append(details)


def test_accept():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 0))
    sock.listen()
    port = sock.getsockname()[1]

    result = []
    thread = Thread(target=accept, args=(sock, result))
    thread.start()

    j = wsjoiner.WAMPSessionJoiner()
    client_base_session = j.join(f"ws://localhost:{port}/ws", "realm1")
    client_base_session.ws.close()

    thread.join()
    server_base_session = result[0]

    assert client_base_session.realm == server_base_session.realm
    assert client_base_session.authid == server_base_session.authid
    assert client_base_session.authrole == server_base_session.authrole
