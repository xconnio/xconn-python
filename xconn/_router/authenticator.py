from wampproto import auth
from xconn._router.types import Authenticators


class ServerAuthenticator(auth.IServerAuthenticator):
    anonymous = "anonymous"
    ticket = "ticket"
    wampCRA = "wampcra"
    cryptosign = "cryptosign"

    def __init__(self, authenticators: Authenticators):
        self.authenticators = authenticators

    def authenticate(self, request: auth.Request) -> auth.Response:
        match request.method:
            case ServerAuthenticator.anonymous:
                for anonymous in self.authenticators.anonymous:
                    if anonymous.realm == request.realm:
                        return auth.Response(request.authid, request.authrole)
                raise RuntimeError("invalid realm")
            case ServerAuthenticator.ticket:
                for ticket in self.authenticators.ticket:
                    if ticket.realm == request.realm:
                        if ticket.ticket == request.ticket:
                            return auth.Response(request.authid, request.authrole)
                        raise RuntimeError("invalid ticket")
                raise RuntimeError("invalid realm")
            case ServerAuthenticator.wampCRA:
                for wampcra in self.authenticators.wampcra:
                    if wampcra.realm == request.realm:
                        if wampcra.authid == request.authid:
                            if wampcra.salt is not None:
                                return auth.WAMPCRASaltedResponse(
                                    request.authid,
                                    request.authrole,
                                    wampcra.secret,
                                    wampcra.salt,
                                    wampcra.iterations,
                                    wampcra.keylen,
                                )

                            return auth.WAMPCRAResponse(request.authid, request.authrole, wampcra.secret)
                    raise RuntimeError("invalid wampcra secret")
                raise RuntimeError("invalid realm")
            case ServerAuthenticator.cryptosign:
                for cryptosign in self.authenticators.cryptosign:
                    if cryptosign.realm == request.realm:
                        if request.public_key in cryptosign.authorized_keys:
                            return auth.Response(request.authid, request.authrole)
                    raise RuntimeError("unknown publickey")
                raise RuntimeError("unknown realm")
            case _:
                raise RuntimeError(f"unknown authentication method: {request.method}")

    def methods(self):
        return [self.anonymous, self.ticket, self.wampCRA, self.cryptosign]
