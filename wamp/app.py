from typing import Callable


class IApp:
    @property
    def procedures(self) -> dict[str, Callable]:
        raise NotImplementedError()

    def register(self, procedure: str):
        raise NotImplementedError()


class WampApp(IApp):
    def __init__(self):
        super().__init__()
        self._procedures = {}

    @property
    def procedures(self) -> dict[str, Callable]:
        return self._procedures

    def register(self, procedure: str):
        def _register(func):
            if procedure in self._procedures:
                raise ValueError(f"procedure {procedure} already registered")

            self._procedures[procedure] = func

        return _register
