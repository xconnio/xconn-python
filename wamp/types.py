from simple_websocket import Client
from wampproto import joiner, serializers


class BaseSession:
    def __init__(self, ws: Client, session_details: joiner.SessionDetails, serializer: serializers.Serializer):
        super().__init__()
        self.ws = ws
        self.session_details = session_details
        self.serializer = serializer

    def send(self, data: bytes):
        self.ws.send(data)

    def receive(self) -> bytes:
        return self.ws.receive()
