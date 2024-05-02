from wamp.router import Router
from wamp.server import Server

if __name__ == '__main__':
    import uvloop
    uvloop.install()

    r = Router()
    r.add_realm("realm1")
    s = Server(r)
    s.start("0.0.0.0", 8080)
