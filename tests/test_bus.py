from pydantic import BaseModel
from pyaduct import Broker, Client, Event

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
    assert ipc_client_1._topics["test_topic"].get(timeout=2).message == domain_event.message

