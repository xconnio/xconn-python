from pydantic import BaseModel


class InData(BaseModel):
    first_name: str
    last_name: str
    age: int


class OutData(BaseModel):
    first_name: str
    last_name: str
    age: int


class House(BaseModel):
    street: str
    house_number: str


class Address(BaseModel):
    house: House
    city: str
    zip_code: int
    country: str


class EmailData(BaseModel):
    primary_email: str
    secondary_email: str | None = None


class ContactInfo(BaseModel):
    email: EmailData
    phone: str


class UserProfile(BaseModel):
    name: str
    age: int
    address: Address
    contact: ContactInfo
