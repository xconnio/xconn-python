from xconn.types import Depends, CallDetails

from xconn import App

app = App()


async def get_something() -> App:
    return app


@app.register("hello")
async def create_user(first_name: str, last_name:str, something: App = Depends(get_something)):
    print(first_name, last_name, something)
