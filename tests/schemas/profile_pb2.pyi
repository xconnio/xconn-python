from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class ProfileCreate(_message.Message):
    __slots__ = ["age", "email", "username"]
    AGE_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    age: int
    email: str
    username: str
    def __init__(
        self, username: _Optional[str] = ..., email: _Optional[str] = ..., age: _Optional[int] = ...
    ) -> None: ...

class ProfileGet(_message.Message):
    __slots__ = ["age", "created_at", "email", "id", "username"]
    AGE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    EMAIL_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    USERNAME_FIELD_NUMBER: _ClassVar[int]
    age: int
    created_at: str
    email: str
    id: str
    username: str
    def __init__(
        self,
        id: _Optional[str] = ...,
        username: _Optional[str] = ...,
        email: _Optional[str] = ...,
        age: _Optional[int] = ...,
        created_at: _Optional[str] = ...,
    ) -> None: ...
