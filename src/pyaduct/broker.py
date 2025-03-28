import datetime
import threading
import time
from multiprocessing import Queue
from threading import Thread
from typing import Callable
from uuid import UUID

from loguru import logger
from zmq import NOBLOCK, Again, Socket

from .models import Event, Message, Register, Request, Response, Subscribe


class Broker:
    def __init__(self, socket: Socket):
        assert isinstance(socket, Socket)
        self._socket = socket
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
            message_type, body = text.split(" ", 1)
            self._rx_queue.put((client_id, message_type, body), block=False)

    def __handle(self):
        while not self._stop.is_set():
            if self._rx_queue.empty():
                continue
            client_id, message_type, body = self._rx_queue.get(block=False)
            assert isinstance(client_id, bytes)
            message_types = {
                "REQUEST": (Request, self._handle_request),
                "RESPONSE": (Response, self._handle_response),
                "EVENT": (Event, self._handle_event),
                "SUBSCRIBE": (Subscribe, self._handle_subscribe),
                "REGISTER": (Register, self._handle_register),
            }
            model, function = message_types[message_type]
            try:
                message = model.model_validate_json(body)
                assert isinstance(message, Message)
            except Exception as e:
                logger.error(f"Error validating message: {e}")
                return
            function(message, client_id)
            log = f"{self.name} | RX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.trace(log)

    def _handle_register(self, register: Register, client_id: bytes):
        if register.source not in self.clients:
            self.clients[register.source] = client_id
        response = Response(
            source="broker",
            requestor=register.source,
            response="ACK",
            request_id=register.id,
        )
        self._tx_queue.put((response, None), block=False)

    def _handle_subscribe(self, subscribe: Subscribe, client_id: bytes):
        _ = client_id
        if subscribe.topic not in self._topics:
            self._topics[subscribe.topic] = []
        self._topics[subscribe.topic].append(subscribe.source)
        response = Response(
            source="broker",
            requestor=subscribe.source,
            response="ACK",
            request_id=subscribe.id,
        )
        self._tx_queue.put((response, None), block=False)

    def _handle_event(self, event: Event, client_id: bytes):
        _ = client_id
        if event.topic in self._topics:
            for client in self._topics[event.topic]:
                client_id = self.clients[client]
                self._tx_queue.put((event, client_id), block=False)
        else:
            logger.warning(f"No subscribers for topic: {event.topic}")

    def _handle_request(self, request: Request, client_id: bytes):
        if request.target == "broker":
            self._handle_broker_request(request, client_id)
            return
        _ = client_id
        self._tx_queue.put((request, None), block=False)

    def _handle_broker_request(self, request: Request, client_id: bytes):
        clients = ",".join([name for name in self.clients.keys()])
        if request.request == "GET_CLIENTS":
            response = Response(
                response=clients,
                requestor=request.source,
                request_id=request.id,
                source="broker",
            )
        else:
            logger.error(f"Unknown broker request: {request.request}")
            response = Response(
                response="Unknown broker request",
                requestor=request.source,
                request_id=request.id,
                source="broker",
            )
        self._tx_queue.put((response, None), block=False)

    def _handle_response(self, response: Response, client_id: bytes):
        _ = client_id
        self._seen.add(response.request_id)
        self._send_response(response)

    def __send(self):
        while not self._stop.is_set():
            if self._tx_queue.empty():
                continue
            message, client_id = self._tx_queue.get(block=False)
            assert isinstance(message, (Request, Response, Event))
            if isinstance(message, Request):
                self._send_request(message)
            if isinstance(message, Response):
                self._send_response(message)
            if isinstance(message, Event):
                assert isinstance(client_id, bytes)
                self._send_event(message, client_id)
            log = f"{self.name} | TX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.trace(log)

    def _send_request(self, request: Request):
        self._pending[request.id] = request
        text = f"{request.type.value} {request.model_dump_json()}"
        self._socket.send_multipart([self.clients[request.target], b"", text.encode("utf-8")])

    def _send_response(self, response: Response):
        text = f"{response.type.value} {response.model_dump_json()}"
        client_id = self.clients[response.requestor]
        self._socket.send_multipart([client_id, b"", text.encode("utf-8")])

    def _send_event(self, event: Event, client_id: bytes):
        text = f"{event.type.value} {event.model_dump_json()}"
        self._socket.send_multipart([client_id, b"", text.encode("utf-8")])
