import datetime
import json
from enum import Enum
from uuid import UUID, uuid4

from loguru import logger
from pydantic import BaseModel, Field


class MessageType(Enum):
    REQUEST = "REQUEST"
    RESPONSE = "RESPONSE"
    EVENT = "EVENT"
    REGISTER = "REGISTER"
    SUBSCRIBE = "SUBSCRIBE"


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source: str
    type: MessageType

    # timestamp: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
    def generate_datetime() -> datetime.datetime:
        return datetime.datetime.now(datetime.timezone.utc)

    timestamp: datetime.datetime = Field(default_factory=generate_datetime)

    @classmethod
    def from_json(cls, json_str: str):
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON: {json_str}")
            return None
        return cls(**data)


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
