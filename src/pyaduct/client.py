import threading
import time
from multiprocessing import Queue
from threading import Thread
from typing import Callable
from uuid import UUID

from loguru import logger
from pydantic import BaseModel
from zmq import NOBLOCK, Again, Socket

from .models import Event, Message, Register, Request, Response, Subscribe
from .utils import generate_random_md5


class ClientException(Exception):
    pass


class Client:
    def __init__(
        self,
        socket: Socket,
        name: str | None = None,
    ):
        assert isinstance(socket, Socket), "Socket must be of type zmq.Socket"
        self._socket = socket
        if name:
            _name = name
        else:
            _name = generate_random_md5()
        assert isinstance(_name, str), "Name must be of type str"
        self.name: str = _name
        self.registered: bool = False
        self._stop = threading.Event()
        self._threads: dict[str, Thread] = {}
        _threads: dict[str, Callable] = {
            f"{self.name}|Listen": self.__listen,
            f"{self.name}|Handle": self.__handle,
            f"{self.name}|Send": self.__send,
        }
        for name, target in _threads.items():
            thread = Thread(target=target, name=name)
            self._threads[name] = thread
        self._topics: dict[str, Queue] = {}
        self._rx_messages: dict[UUID, Message] = {}
        self._tx_queue: Queue[Message] = Queue()
        self._rx_queue: Queue[tuple[str, str]] = Queue()
        self.requests: Queue[Request] = Queue()

    def start(self):
        for thread in self._threads.values():
            thread.start()
        self._register()
        while not self.registered:
            time.sleep(0.1)
        logger.success(f"{self.name} | Client started: {self.name}")

    def stop(self):
        self._stop.set()
        for thread in self._threads.values():
            thread.join()
        self._socket.close()

    def subscribe(self, topic: str) -> Queue:
        logger.info(f"{self.name} | Subscribing to topic: {topic}")
        subscribe = Subscribe(source=self.name, topic=topic)
        try:
            self._sync_send(subscribe, 2)
        except Exception as e:
            logger.error(f"{self.name} | Failed to subscribe: {e}")
            raise e
        self._topics[topic] = Queue()
        return self._topics[topic]

    def publish(self, event: Event):
        assert isinstance(event, Event), "Event must be of type Event"
        self._tx_queue.put(event, block=False)

    def request(self, request: Request, timeout: int = 5) -> Response:
        assert isinstance(request, Request), "Request must be of type Request"
        return self._sync_send(request, timeout)

    def generate_request(
        self,
        target: str,
        request: Request,
        timeout: int = 5,
    ) -> Request:
        """Builds a Request so that the source is already populated."""
        request_str: str = request.model_dump_json()
        return Request(source=self.name, target=target, request=request_str, timeout=timeout)

    def generate_event(self, topic: str, event: BaseModel) -> Event:
        """Builds an Event so that the source is already populated."""
        event_str: str = event.model_dump_json()
        return Event(source=self.name, topic=topic, event=event_str)

    def respond(self, request: Request, message: str) -> None:
        response = Response(
            source=self.name,
            requestor=request.source,
            response=message,
            request_id=request.id,
        )
        self._tx_queue.put(response, block=False)

    def _register(self):
        """Register with the broker."""
        timeout: int = 2
        register = Register(source=self.name)
        try:
            self._sync_send(register, timeout)
        except Exception as e:
            logger.error(f"{self.name} | Failed to register: {e}")
            return
        self.registered = True

    def _sync_send(self, message: Request | Register | Subscribe, timeout: int) -> Response:
        """Synchronous send. Waits for response."""
        self._tx_queue.put(message, block=False)
        assert isinstance(message, Request | Register | Subscribe), (
            "Message must be of type Request or Register or Subscribe"
        )
        del_id: UUID | None = None
        for _ in range(timeout * 10):
            for rx_msg in self._rx_messages.values():
                assert isinstance(rx_msg, Message)
                if isinstance(rx_msg, Response):
                    if rx_msg.request_id == message.id:
                        del_id = message.id
                        return rx_msg
            time.sleep(0.1)
        if del_id is not None:
            logger.success(f"{self.name} | Response received for request: {message.id}")
            del self._rx_messages[del_id]
        else:
            logger.error(f"{self.name} | Timeout waiting for response for request: {message.id}")
            raise ClientException("Request timed out")

    def __listen(self):
        """Listen for messages from the broker."""
        while not self._stop.is_set():
            try:
                text = self._socket.recv(flags=NOBLOCK)
            except Again:
                continue
            if not text:
                continue
            # logger.debug(f"{self.name} | RX: {text}")
            text = text.decode("utf-8")
            message_type, body = text.split(" ", 1)
            self._rx_queue.put((message_type, body), block=False)

    def __handle(self):
        """Handle incoming messages."""
        while not self._stop.is_set():
            if self._rx_queue.empty():
                continue
            message_type, body = self._rx_queue.get(block=False)
            if message_type == "RESPONSE":
                message = Response.model_validate_json(body)
            elif message_type == "EVENT":
                message = Event.model_validate_json(body)
                if message.topic in self._topics:
                    self._topics[message.topic].put(message, block=False)
            elif message_type == "REQUEST":
                message = Request.model_validate_json(body)
                # Ping/pong handled directly by client and not put into
                # the request queue.
                if message.request == "PING":
                    response = Response(
                        source=self.name,
                        requestor=message.source,
                        response="PONG",
                        request_id=message.id,
                    )
                    self._tx_queue.put(response, block=False)
                else:
                    self.requests.put(message, block=False)
            else:
                raise Exception(f"Client does not support message type: {message_type}")
            self._rx_messages[message.id] = message
            log = f"{self.name} | RX: {message_type}\n"
            log += f"{message.model_dump_json(indent=2)}"
            # logger.debug(log)

    def __send(self):
        """Send messages to the broker."""
        while not self._stop.is_set():
            if self._tx_queue.empty():
                continue
            message = self._tx_queue.get(block=False)
            assert isinstance(message, Message)
            body = f"{message.type.value} {message.model_dump_json()}"
            self._socket.send_string(body)
            log = f"{self.name} | TX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            # logger.debug(log)
