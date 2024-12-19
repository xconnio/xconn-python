class ApplicationError(Exception):
    def __init__(self, message: str, args: list | None = None, kwargs: dict | None = None):
        super().__init__(message)
        self.message = message
        self.__args = args
        self.kwargs = kwargs

    @property
    def args(self):
        return self.__args

    def __str__(self):
        err = self.message
        if self.args:
            args = ", ".join(str(arg) for arg in self.args)
            err += f": {args}"
        if self.kwargs:
            kwargs = ", ".join(f"{key}={value}" for key, value in self.kwargs.items())
            err += f": {kwargs}"
        return err
