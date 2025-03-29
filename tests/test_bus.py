from pydantic import BaseModel

from pyaduct import Broker, Client


class DomainEvent(BaseModel):
    message: str = "Hello, World!"


def test_ipc_bus(
    ipc_broker: Broker,
    ipc_client_1: Client,
    ipc_client_2: Client,
):
    """Test the IPC broker."""
    domain_event = DomainEvent()
    ipc_client_1.subscribe("test_topic")
    ipc_client_2.generate_event("test_topic", domain_event)


def test_tcp_bus(
    tcp_broker: Broker,
    tcp_client_1: Client,
    tcp_client_2: Client,
):
    """Test the TCP broker."""
    domain_event = DomainEvent()
    tcp_client_1.subscribe("test_topic")
    tcp_client_2.generate_event("test_topic", domain_event)
    assert tcp_client_1.ping("client_2")
