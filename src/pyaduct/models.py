import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from .utils import generate_datetime, generate_uuid7


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
    id: UUID = Field(default_factory=generate_uuid7)
    type: MessageType
    timestamp: datetime.datetime = Field(default_factory=generate_datetime)
    source: str


class Register(Message):
    type: MessageType = MessageType.REGISTER


class Request(Message):
    type: MessageType = MessageType.REQUEST
    target: str
    timeout: int = 5
    body: str


class Response(Message):
    request_id: UUID
    type: MessageType = MessageType.RESPONSE
    requestor: str
    body: str


class Event(Message):
    type: MessageType = MessageType.EVENT
    topic: str
    body: str


class Subscribe(Message):
    type: MessageType = MessageType.SUBSCRIBE
    topic: str


class Ping(Request):
    type: MessageType = MessageType.PING
    body: str = "Ping"


class Pong(Response):
    type: MessageType = MessageType.PONG
    body: str = "Pong"


class ACK(Response):
    type: MessageType = MessageType.ACK
    body: str = "ACK"
