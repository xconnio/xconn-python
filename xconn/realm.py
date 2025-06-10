from asyncio import gather

from wampproto import dealer, broker, messages
from wampproto.types import SessionDetails

from xconn import types, uris


class Realm:
    def __init__(self):
        super().__init__()
        self.dealer = dealer.Dealer()
        self.broker = broker.Broker()

        self.clients: dict[int, types.IAsyncBaseSession] = {}

    def attach_client(self, base: types.IAsyncBaseSession):
        self.clients[base.id] = base

        details = SessionDetails(base.id, base.realm, base.authid, base.authrole)
        self.dealer.add_session(details)
        self.broker.add_session(details)

    def detach_client(self, base: types.IAsyncBaseSession):
        del self.clients[base.id]
        self.broker.remove_session(base.id)
        self.dealer.remove_session(base.id)

    def stop(self):
        """stop will disconnect all clients."""
        pass

    async def receive_message(self, session_id: int, msg: messages.Message):
        match msg.TYPE:
            case (
                messages.Call.TYPE
                | messages.Yield.TYPE
                | messages.Register.TYPE
                | messages.Unregister.TYPE
                | messages.Error.TYPE
            ):
                recipient = self.dealer.receive_message(session_id, msg)
                client = self.clients[recipient.recipient]
                await client.send_message(recipient.message)

            case messages.Publish.TYPE:
                publication = self.broker.receive_publish(session_id, msg)

                if len(publication.recipients) != 0:
                    tasks = []
                    for recipient in publication.recipients:
                        client = self.clients[recipient]
                        tasks.append(client.send_message(publication.event))

                    await gather(*tasks)

                if publication.ack is not None:
                    client = self.clients[publication.ack.recipient]
                    await client.send_message(publication.ack.message)

            case messages.Subscribe.TYPE | messages.Unsubscribe.TYPE:
                recipient = self.broker.receive_message(session_id, msg)
                client = self.clients[recipient.recipient]
                await client.send_message(recipient.message)
            case messages.Goodbye.TYPE:
                self.dealer.remove_session(session_id)
                self.broker.remove_session(session_id)
                try:
                    client = self.clients.pop(session_id)
                except KeyError:
                    return

                goodbye = messages.Goodbye(messages.GoodbyeFields({}, uris.CLOSE_GOODBYE_AND_OUT))
                await client.send_message(goodbye)
                await client.close()
