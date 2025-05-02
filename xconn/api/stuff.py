from typing import Annotated
from pydantic import BaseModel
from pydantic.dataclasses import dataclass, is_pydantic_dataclass


@dataclass
class Test:
    username: str
    password: str

    city: "City"
    country: str | None = None


@dataclass
class City:
    name: str
    country: str | None = None


class UserCreate(BaseModel):
    username: str
    password: str

    city: str | None = None
    country: str | None = None


def get_db() -> str:
    pass


def get_session():
    pass


class Depends:
    def __init__(self, dependency):
        super().__init__()
        self.dependency = dependency


IGNORE_TYPES = (str, int, float, bool, list, dict, tuple, set)


def create_user(
    request: UserCreate, db: Annotated[str, Depends(get_db)], session: Annotated[str, Depends(get_session)]
):
    pass


def validate_func(func):
    import inspect

    sig = inspect.signature(func)
    for name, param in sig.parameters.items():
        print(name, is_pydantic_dataclass(param.annotation))


if __name__ == "__main__":
    validate_func(create_user)
