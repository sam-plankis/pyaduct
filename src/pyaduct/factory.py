from zmq import DEALER, ROUTER, Context

from .broker import Broker
from .client import Client
from .store import InmemBrokerStore


class BrokerFactory:
    @classmethod
    def generate_ipc_broker(cls) -> Broker:
        """Generate an IPC broker."""
        address = "ipc://pyaduct"
        context = Context()
        socket = context.socket(ROUTER)
        socket.bind(address)
        store = InmemBrokerStore()
        broker = Broker(socket, store=store, latency=(0.3, 0.7))
        return broker


class ClientFactory:
    @classmethod
    def generate_ipc_client(cls, client_name: str) -> Client:
        """Generate an IPC client with the given name."""
        assert isinstance(client_name, str), "Client name must be a string"
        context = Context()
        socket = context.socket(DEALER)
        address = "ipc://pyaduct"
        socket.connect(address)
        client = Client(socket, name=client_name)
        return client


class PyaductFactory:
    @classmethod
    def generate_ipc_nodes(cls) -> tuple[Broker, Client, Client]:
        """Generate a system with a broker and two clients."""
        broker = BrokerFactory.generate_ipc_broker()
        client_1 = ClientFactory.generate_ipc_client("client_1")
        client_2 = ClientFactory.generate_ipc_client("client_2")
        return broker, client_1, client_2
