import datetime
import random
import threading
import time
from multiprocessing import Queue
from threading import Thread
from typing import Callable
from uuid import UUID

from loguru import logger
from zmq import NOBLOCK, Again, Socket

from .models import (
    ACK,
    Command,
    Event,
    Message,
    Ping,
    Pong,
    Register,
    Request,
    Response,
    Subscribe,
)
from .store import IBrokerStore


class BrokerError(BaseException):
    """Custom exception for Broker errors."""

    pass


class Broker:
    def __init__(
        self,
        socket: Socket,
        store: IBrokerStore | None = None,
        latency: tuple[float, float] | None = None,
    ):
        assert isinstance(socket, Socket)
        self._latency = latency
        self._socket = socket
        self.store: IBrokerStore | None = store
        self.clients: dict[str, bytes] = {}
        self._stop = threading.Event()
        self._threads: dict[str, Thread] = {}
        _threads: dict[str, Callable] = {
            "Broker|Listen": self.__listen,
            "Broker|Send": self.__send,
            "Broker|Handle": self.__handle,
            "Broker|Watch": self.__watch,
        }
        for name, target in _threads.items():
            thread = Thread(target=target, name=name)
            self._threads[name] = thread
        self._topics: dict[str, list] = {}
        self._pending: dict[UUID, Request] = {}
        self._seen: set[UUID] = set()
        self._tx_queue: Queue[tuple[Event | Request | Response, bytes | None]] = Queue()
        self._rx_queue: Queue[tuple[bytes | None, str, str]] = Queue()
        self.name: str = "Broker"

    def start(self):
        for thread in self._threads.values():
            thread.start()
        logger.success("Broker started")

    def stop(self):
        self._stop.set()
        for thread in self._threads.values():
            thread.join()
        self._socket.close()
        logger.success("Broker stopped")

    def __watch(self):
        while not self._stop.is_set():
            for request_id, request in list(self._pending.items()):
                if request_id in self._seen:
                    logger.trace(f"Response for request succeeded: {request_id}")
                    self._seen.remove(request_id)
                    del self._pending[request_id]
                    continue
                now = datetime.datetime.now(datetime.timezone.utc)
                delta = datetime.timedelta(seconds=request.timeout)
                if request.timestamp < now - delta:
                    logger.warning(f"Response for request timed out: {request_id}")
                    del self._pending[request_id]
            time.sleep(0.1)

    def __listen(self):
        while not self._stop.is_set():
            try:
                client_id, text = self._socket.recv_multipart(flags=NOBLOCK)
            except Again:
                continue
            if not text:
                continue
            text = text.decode("utf-8")
            message_type, model = text.split(" ", 1)
            self._rx_queue.put((client_id, message_type, model), block=False)

    def __handle(self):
        while not self._stop.is_set():
            if self._rx_queue.empty():
                continue
            client_id, message_type, rx_model = self._rx_queue.get(block=False)
            assert isinstance(client_id, bytes)
            message_types = {
                "COMMAND": (Command, self._handle_command),
                "REQUEST": (Request, self._handle_request),
                "RESPONSE": (Response, self._handle_response),
                "EVENT": (Event, self._handle_event),
                "SUBSCRIBE": (Subscribe, self._handle_subscribe),
                "REGISTER": (Register, self._handle_register),
                "PING": (Ping, self._handle_request),
                "PONG": (Pong, self._handle_response),
            }
            assert message_type in message_types, f"Unknown message type: {message_type}"
            model, function = message_types[message_type]
            assert issubclass(model, Message)
            assert isinstance(function, Callable)
            try:
                message = model.model_validate_json(rx_model)
                assert isinstance(message, Message)
            except Exception as e:
                logger.error(f"Error validating message: {e}")
                return
            function(message, client_id)
            log = f"\n# {self.name} | RX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.trace(log)

    def _handle_register(self, register: Register, client_id: bytes):
        if self.store:
            self.store.add_message(register)
        if register.source not in self.clients:
            self.clients[register.source] = client_id
        ack = ACK(
            source="broker",
            requestor=register.source,
            request_id=register.id,
        )
        self._tx_queue.put((ack, None), block=False)
        if self.store:
            self.store.add_message(ack)

    def _handle_subscribe(self, subscribe: Subscribe, client_id: bytes):
        if self.store:
            self.store.add_message(subscribe)
        _ = client_id
        if subscribe.topic not in self._topics:
            self._topics[subscribe.topic] = []
        self._topics[subscribe.topic].append(subscribe.source)
        response = ACK(
            source="broker",
            requestor=subscribe.source,
            request_id=subscribe.id,
        )
        self._tx_queue.put((response, None), block=False)
        if self.store:
            self.store.add_message(response)

    def _handle_event(self, event: Event, client_id: bytes):
        _ = client_id
        if event.topic in self._topics:
            for client in self._topics[event.topic]:
                client_id = self.clients[client]
                self._tx_queue.put((event, client_id), block=False)
                if self.store:
                    self.store.add_message(event)
        else:
            logger.warning(f"No subscribers for topic: {event.topic}")

    def _handle_request(self, request: Request, client_id: bytes):
        _ = client_id
        self._tx_queue.put((request, None), block=False)
        if self.store:
            self.store.add_message(request)

    def _handle_command(self, command: Command, client_id: bytes):
        _ = client_id  # We don't use client_id for commands
        current_client = command.source
        if command.body == "GET_CLIENTS":
            clients = ",".join([name for name in self.clients.keys() if name != current_client])
            response = Response(
                body=clients,
                requestor=command.source,
                request_id=command.id,
                source="broker",
            )
            self._tx_queue.put((response, None), block=False)
            if self.store:
                self.store.add_message(response)

    def _handle_response(self, response: Response, client_id: bytes):
        _ = client_id
        self._seen.add(response.request_id)
        self._send_response(response)
        if self.store:
            self.store.add_message(response)

    def __send(self):
        while not self._stop.is_set():
            if self._tx_queue.empty():
                continue
            message, client_id = self._tx_queue.get(block=False)
            assert isinstance(message, (Request, Response, Event, Ping, Pong, ACK))
            if isinstance(message, Request):
                self._send_request(message)
            elif isinstance(message, Response):
                self._send_response(message)
            elif isinstance(message, Event):
                assert isinstance(client_id, bytes)
                self._send_event(message, client_id)
            elif isinstance(message, Ping):
                assert isinstance(client_id, bytes)
                self._send_request(message)
            elif isinstance(message, Pong):
                assert isinstance(client_id, bytes)
                self._send_response(message)
            elif isinstance(message, ACK):
                assert isinstance(client_id, bytes)
                self._send_response(message)
            else:
                logger.error(f"Unknown message type: {type(message)}")
                raise BrokerError(f"Unknown message type: {type(message)}")
            log = f"\n# {self.name} | TX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.trace(log)

    def _send_request(self, request: Request):
        self._pending[request.id] = request
        text = f"{request.type.value} {request.model_dump_json()}"
        target = self.clients.get(request.target)
        if target is None:
            logger.error(f"Unknown target: {request.target}")
            return
        client_id = self.clients[request.target]
        # self._socket.send_multipart([self.clients[request.target], b"", text.encode("utf-8")])
        self._send_multipart(client_id, text)

    def _send_response(self, response: Response):
        text = f"{response.type.value} {response.model_dump_json()}"
        client_id = self.clients[response.requestor]
        # self._socket.send_multipart([client_id, b"", text.encode("utf-8")])
        self._send_multipart(client_id, text)

    def _send_event(self, event: Event, client_id: bytes):
        text = f"{event.type.value} {event.model_dump_json()}"
        # self._socket.send_multipart([client_id, b"", text.encode("utf-8")])
        self._send_multipart(client_id, text)

    def _send_multipart(self, client_id: bytes, text: str):
        if self._latency:
            lower, upper = self._latency
            random_sleep = random.uniform(lower, upper)
            time.sleep(random_sleep)
        assert isinstance(client_id, bytes)
        assert isinstance(text, str)
        self._socket.send_multipart([client_id, b"", text.encode("utf-8")])
