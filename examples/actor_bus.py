import random
import time
from threading import Event as ThreadEvent
from threading import Thread
from typing import Callable

from loguru import logger

from pyaduct import BrokerFactory, ClientFactory
from pyaduct.client import Client

logger.enable("pyaduct")


class Actor:
    def __init__(self, client: Client, functions: list[Callable]):
        self.client = client
        self.name = client.name
        self.thread: Thread = Thread(target=self.run, name=self.name)
        self._stop: ThreadEvent = ThreadEvent()
        self.function = functions

    def start(self):
        self.client.start()
        self.thread.start()

    def stop(self):
        self._stop.set()
        self.thread.join()
        self.client.stop()
        print(f"Actor {self.name} has stopped.")

    def run(self, interval: int = 1):
        while not self._stop.is_set():
            for func in self.function:
                func()
            time.sleep(interval)


class Reporter(Actor):
    def __init__(self, client: Client):
        super().__init__(client, [self.report_system])

    def report_system(self):
        if random.random() < 0.5:
            topic = "SystemReport"
            body = "System is running smoothly"
        else:
            topic = "SystemReport"
            body = "System is experiencing issues"
        event = self.client.generate_event(topic, body)
        self.client.publish(event)


class Server(Actor):
    def __init__(self, client: Client):
        self.events = client.subscribe("SystemReport")
        super().__init__(client, [self.handle_events])

    def handle_events(self):
        if self.events.empty():
            return
        event = self.events.get(timeout=1)
        print(f"Server {self.name} received event: {event}")


class Worker(Actor):
    def __init__(self, client: Client):
        super().__init__(client, [self.ping_server])

    def ping_server(self):
        if self.client.ping("server"):
            print(f"Worker {self.name} pinged server successfully")
        else:
            print(f"Worker {self.name} failed to ping server")
        time.sleep(1)


if __name__ == "__main__":
    broker = BrokerFactory.generate_ipc_broker()
    broker.start()
    time.sleep(0.1)
    # Server
    server_client = ClientFactory.generate_ipc_client("server")
    server = Server(server_client)
    server.start()
    time.sleep(0.1)
    # Reporter
    reporter_client = ClientFactory.generate_ipc_client("reporter")
    reporter = Reporter(reporter_client)
    reporter.start()
    time.sleep(0.1)
    # Worker
    worker_client = ClientFactory.generate_ipc_client("worker")
    worker = Worker(worker_client)
    worker.start()
    time.sleep(0.1)
    input("Press Enter to stop the actors...")
    reporter.stop()
    server.stop()
    broker.stop()
    print("All actors have stopped.")
    for thread in [reporter.thread, server.thread, worker.thread]:
        thread.join()
