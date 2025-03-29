from typing import Protocol
from uuid import UUID

from .models import Message


class IBrokerStore(Protocol):
    def add_message(self, message: Message) -> None:
        """Add a message to the store."""
        ...

    def get_message(self, message_id: UUID) -> Message | None:
        """Retrieve a message by its ID."""
        ...

    def delete_message(self, message_id: UUID) -> None:
        """Delete a message from the store."""
        ...

    def add_client(self, client_name: str) -> None:
        """Add a client to the store."""
        ...

    def add_subscriber(self, client_name: str, topic: str) -> None:
        """Add a subscriber for a specific topic."""
        ...

    @property
    def messages(self) -> list[Message]:
        """Return an iterator over the messages in the store."""
        ...

    @property
    def clients(self) -> list[str]:
        """Return an iterator over the clients in the store."""
        ...

    @property
    def subscribers(self) -> dict[str, list[str]]:
        """Return an iterator over the subscribers and their topics."""
        ...


class InmemBrokerStore(IBrokerStore):
    """In-memory message store implementation."""

    def __init__(self):
        self._messages: list[Message] = []
        self._clients: list[str]
        self._subscribers: dict[str, list[str]] = {}

    def add_client(self, client_name: str) -> None:
        if client_name not in self._clients:
            self._clients.append(client_name)

    def add_subscriber(self, client_name: str, topic: str) -> None:
        if client_name not in self._clients:
            self.add_client(client_name)
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if client_name not in self._subscribers[topic]:
            self._subscribers[topic].append(client_name)

    def add_message(self, message: Message) -> None:
        self._messages.append(message)

    def get_message(self, message_id: UUID) -> Message | None:
        for message in self._messages:
            if message.id == message_id:
                return message

    def delete_message(self, message_id: UUID) -> None:
        if message_id in self._messages:
            del self._messages[message_id]

    @property
    def messages(self) -> list[Message]:
        return self._messages

    @property
    def clients(self) -> list[str]:
        return self._clients

    @property
    def subscribers(self) -> dict[str, list[str]]:
        return self._subscribers
