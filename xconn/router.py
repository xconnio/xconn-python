from wampproto import messages

from xconn import realm, types


class Router:
    def __init__(self):
        super().__init__()
        self.realms: dict[str, realm.Realm] = {}

    def add_realm(self, name: str):
        self.realms[name] = realm.Realm()

    def remove_realm(self, name: str):
        del self.realms[name]

    def has_realm(self, name: str):
        return name in self.realms

    def attach_client(self, base_session: types.IAsyncBaseSession):
        if base_session.realm not in self.realms:
            raise ValueError(f"cannot attach client to non-existent realm {base_session.realm}")

        self.realms[base_session.realm].attach_client(base_session)

    def detach_client(self, base_session: types.IAsyncBaseSession):
        if base_session.realm not in self.realms:
            raise ValueError(f"cannot detach client from non-existent realm {base_session.realm}")

        self.realms[base_session.realm].detach_client(base_session)

    async def receive_message(self, base_session: types.IAsyncBaseSession, msg: messages.Message):
        if base_session.realm not in self.realms:
            raise ValueError(f"cannot process message for non-existent realm {base_session.realm}")

        await self.realms[base_session.realm].receive_message(base_session.id, msg)
