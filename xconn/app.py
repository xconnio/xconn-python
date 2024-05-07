from typing import Callable


class IApp:
    @property
    def procedures(self) -> dict[str, Callable]:
        raise NotImplementedError()

    def include_app(self, app: "IApp") -> None:
        raise NotImplementedError()

    def register(self, procedure: str):
        raise NotImplementedError()


class XConnApp(IApp):
    def __init__(self):
        super().__init__()
        self._procedures = {}

    @property
    def procedures(self) -> dict[str, Callable]:
        return self._procedures

    def include_app(self, app: "IApp", prefix: str = "") -> None:
        if prefix is None or len(prefix) == 0:
            self._procedures.update(app.procedures)
        else:
            for procedure, func in app.procedures.items():
                self._procedures.update({prefix + procedure: func})

    def register(self, procedure: str):
        def _register(func):
            if procedure in self._procedures:
                raise ValueError(f"procedure {procedure} already registered")

            self._procedures[procedure] = func

        return _register
