from concurrent.futures import ThreadPoolExecutor
import socket

from wamp.router import Router
from wamp.wsacceptor import WAMPSessionAcceptor


class Server:
    def __init__(self, router: Router):
        self.executor = ThreadPoolExecutor(max_workers=100)
        self.router = router

    def start(self, host: str, port: int):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            s.listen()
            while True:
                conn, addr = s.accept()
                self.executor.submit(self.process_connection, conn)

    def process_connection(self, conn: socket.socket):
        acceptor = WAMPSessionAcceptor()
        base_session = acceptor.accept(conn)
        self.router.attach_client(base_session)
        while True:
            msg = base_session.receive_message()
            self.router.receive_message(base_session, msg)
