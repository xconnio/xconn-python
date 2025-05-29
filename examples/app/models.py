from pydantic import BaseModel


class InData(BaseModel):
    first_name: str
    last_name: str
    age: int


class OutData(BaseModel):
    first_name: str
    last_name: str
    age: int
