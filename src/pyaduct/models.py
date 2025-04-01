import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .utils import generate_datetime, generate_uuid7


class MessageType(Enum):
    COMMAND = "COMMAND"
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    REGISTER = "REGISTER"
    SUBSCRIBE = "SUBSCRIBE"
    PING = "PING"
    PONG = "PONG"
    ACK = "ACK"


class Message(BaseModel):
    id: UUID = Field(default_factory=generate_uuid7)
    type: MessageType
    timestamp: datetime.datetime = Field(default_factory=generate_datetime)
    source: str
    body: str


class Register(Message):
    type: MessageType = MessageType.REGISTER
    body: str = "REGISTER"


class Request(Message):
    type: MessageType = MessageType.REQUEST
    target: str
    timeout: int = 5


class Command(Request):
    type: MessageType = MessageType.COMMAND


class Response(Message):
    request_id: UUID
    type: MessageType = MessageType.RESPONSE
    requestor: str


class Event(Message):
    type: MessageType = MessageType.EVENT
    topic: str


class Subscribe(Message):
    type: MessageType = MessageType.SUBSCRIBE
    topic: str
    body: str = "SUBSCRIBE"


class Ping(Request):
    type: MessageType = MessageType.PING
    body: str = "PING"


class Pong(Response):
    type: MessageType = MessageType.PONG
    body: str = "PONG"


class ACK(Response):
    type: MessageType = MessageType.ACK
    body: str = "ACK"
