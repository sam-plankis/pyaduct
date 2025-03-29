from pyaduct import Broker, Client, Event


def test_ipc_bus(
    ipc_broker: Broker,
    ipc_client_1: Client,
    ipc_client_2: Client,
):
    """Test the IPC broker."""
    client_1_event_queue = ipc_client_1.subscribe("test_topic")
    event = ipc_client_2.generate_event("test_topic", "hello world")
    ipc_client_2.publish(event)
    rx_event = client_1_event_queue.get(timeout=2)
    assert isinstance(rx_event, Event)
    assert event.body == "hello world"


# def test_tcp_bus(
#     tcp_broker: Broker,
#     tcp_client_1: Client,
#     tcp_client_2: Client,
# ):
#     """Test the TCP broker."""
#     domain_event = DomainEvent()
#     tcp_client_1.subscribe("test_topic")
#     tcp_client_2.generate_event("test_topic", domain_event)
#     assert tcp_client_1.ping("client_2")
