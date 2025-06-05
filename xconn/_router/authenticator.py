from wampproto import auth
from xconn._router.types import Authenticators


class ServerAuthenticator(auth.IServerAuthenticator):
    anonymous = "anonymous"
    ticket = "ticket"
    wampCRA = "wampcra"
    cryptosign = "cryptosign"

    def __init__(self, authenticators: Authenticators):
        self.authenticators = authenticators

    def authenticate(self, request: auth.Request):
        match request:
            case auth.AnonymousRequest:
                return auth.Response(request.authid, self.anonymous)
            case auth.TicketRequest:
                for ticket in self.authenticators.ticket:
                    if ticket.realm == request.realm and ticket.ticket == request.ticket:
                        return auth.Response(request.authid, request.authrole)
        if isinstance(request, auth.AnonymousRequest):
            return auth.Response(request.authid, self.anonymous)
        elif isinstance(request, auth.TicketRequest):
            if request.ticket == "test":
                return auth.Response(request.authid, self.ticket)
        elif isinstance(request, auth.WAMPCRARequest):
            return auth.WAMPCRAResponse(request.authid, self.wampCRA, "test")
        elif isinstance(request, auth.CryptoSignRequest):
            if request.public_key == "f79065f0338a395ed7cadd290fe33200d4598bd9ca1350222f980e89d693bed6":
                return auth.Response(request.authid, self.cryptosign)
            raise Exception("unknown publickey")
        raise Exception("unknown authmethod 1")

    def methods(self):
        return [self.anonymous, self.ticket, self.wampCRA, self.cryptosign]
