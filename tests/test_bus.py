from pyaduct import Broker, Client, Event
from pyaduct.store import IMessageStore


def test_ipc_bus(
    ipc_broker: Broker,
    ipc_client_1: Client,
    ipc_client_2: Client,
):
    """Test the IPC bus."""
    assert isinstance(ipc_broker.store, IMessageStore)
    assert isinstance(ipc_client_1.store, IMessageStore)
    assert isinstance(ipc_client_2.store, IMessageStore)
    client_1_event_queue = ipc_client_1.subscribe("test_topic")
    event = ipc_client_2.generate_event("test_topic", "hello world")
    ipc_client_2.publish(event)
    rx_event = client_1_event_queue.get(timeout=2)
    assert isinstance(rx_event, Event)
    assert event.body == "hello world"
    assert ipc_client_1.ping("client_2")
    assert len(ipc_broker.store) == 9
    assert ipc_client_1.get_clients() == ["client_2"]
