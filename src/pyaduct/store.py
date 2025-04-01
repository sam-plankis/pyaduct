from typing import Generator, Protocol, runtime_checkable
from uuid import UUID

from .models import Message


@runtime_checkable
class IMessageStore(Protocol):
    def add_tx_message(self, message: Message) -> None:
        """Add a message to the RX store."""
        ...

    def add_rx_message(self, message: Message) -> None:
        """Add a message to the RX store."""
        ...

    def __contains__(self, message_id: UUID) -> bool:
        """Check if a message is in the store."""
        ...

    def __delitem__(self, message_id: UUID) -> None:
        """Delete a message by ID."""
        ...

    def __getitem__(self, message_id: UUID) -> Message | None:
        """Get a message by ID."""
        ...

    def __iter__(self) -> Generator[Message, None, None]:
        """Iterate over messages in the store."""
        ...

    def __len__(self) -> int:
        """Get the number of messages in the store."""
        ...

    def __repr__(self) -> str:
        """Get a string representation of the store."""
        ...


class InmemMessageStore(IMessageStore):
    """In-memory message store implementation."""

    def __init__(self):
        self._rx_messages: dict[UUID, Message] = {}
        self._tx_messages: dict[UUID, Message] = {}

    def add_tx_message(self, message: Message) -> None:
        self._tx_messages[message.id] = message

    def add_rx_message(self, message: Message) -> None:
        self._tx_messages[message.id] = message

    def __contains__(self, message_id: UUID) -> bool:
        return message_id in self._rx_messages or message_id in self._tx_messages

    def __delitem__(self, message_id: UUID) -> None:
        """Allow dictionary-like deletion of messages."""
        if message_id in self._rx_messages:
            del self._rx_messages[message_id]
        elif message_id in self._tx_messages:
            del self._tx_messages[message_id]
        else:
            raise KeyError(f"Message with ID {message_id} not found.")

    def __getitem__(self, message_id: UUID) -> Message | None:
        """Allow dictionary-like access to messages."""
        if message_id in self._rx_messages:
            return self._rx_messages[message_id]
        if message_id in self._tx_messages:
            return self._tx_messages[message_id]

    def __iter__(self) -> Generator[Message, None, None]:
        rx = list(self._rx_messages.values())
        tx = list(self._tx_messages.values())
        both = rx + tx
        for message in sorted(both, key=lambda message: message.id):
            yield message

    def __len__(self) -> int:
        return len(self._rx_messages) + len(self._tx_messages)

    def __repr__(self) -> str:
        """Provide a developer-friendly string representation."""
        return f"<InmemMessageStore(rx_messages={len(self._rx_messages)}, tx_messages={len(self._tx_messages)})>"
