from pydantic import BaseModel
from xconn import App

app = App()


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    age: int = 0


@app.register("hello")
async def create_user(data: UserCreate):
    print(data)
