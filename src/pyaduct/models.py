import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .utils import generate_datetime


class MessageType(Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    REGISTER = "REGISTER"
    SUBSCRIBE = "SUBSCRIBE"
    PING = "PING"
    PONG = "PONG"
    ACK = "ACK"


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    type: MessageType
    timestamp: datetime.datetime = Field(default_factory=generate_datetime)
    source: str


class Register(Message):
    type: MessageType = MessageType.REGISTER


class Request(Message):
    type: MessageType = MessageType.REQUEST
    target: str
    request: str
    timeout: int = 5


class Response(Message):
    request_id: UUID
    type: MessageType = MessageType.RESPONSE
    requestor: str
    response: str


class Event(Message):
    type: MessageType = MessageType.EVENT
    topic: str
    event: str


class Subscribe(Message):
    type: MessageType = MessageType.SUBSCRIBE
    topic: str


class Ping(Request):
    type: MessageType = MessageType.PING
    request: str = "Ping"


class Pong(Response):
    type: MessageType = MessageType.PONG
    response: str = "Pong"


class ACK(Response):
    type: MessageType = MessageType.ACK
    response: str = "ACK"
