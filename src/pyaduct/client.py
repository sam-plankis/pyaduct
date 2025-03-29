import threading
import time
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Queue
from threading import Thread
from typing import Callable
from uuid import UUID

from loguru import logger
from zmq import NOBLOCK, Again, Socket

from .models import ACK, Event, Message, MessageType, Ping, Pong, Register, Request, Response, Subscribe
from .utils import generate_random_md5


class ClientException(Exception): ...


class ResponseTimeout(ClientException): ...


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
        self._pending_requests: dict[UUID, Message] = {}
        self._tx_queue: Queue[Message] = Queue()
        self._rx_queue: Queue[Message] = Queue()
        self.requests: Queue[Request] = Queue()
        self.responses: dict[UUID, Response] = {}
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=10)

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
            thread = Thread(target=self._sync_send, args=(subscribe, 2))
            thread.start()
        except Exception as e:
            logger.error(f"{self.name} | Failed to subscribe: {e}")
            raise e
        self._topics[topic] = Queue()
        return self._topics[topic]

    def ping(self, target: str) -> bool:
        """Ping a target and wait for a PONG response."""
        ping = Ping(source=self.name, target=target, request="PING")
        if response := self._sync_send(ping, 2):
            if response.type == MessageType.PONG:
                logger.success(f"{self.name} | PING successful to : {target}")
                return True
        logger.warning(f"{self.name} | PING failed to : {target}")
        return False

    def publish(self, event: Event):
        assert isinstance(event, Event), "Event must be of type Event"
        self._tx_queue.put(event, block=False)

    def request(self, request: Request, timeout: int = 5) -> Response | None:
        assert isinstance(request, Request), "Request must be of type Request"
        if response := self._sync_send(request, timeout):
            return response

    def generate_request(
        self,
        target: str,
        body: str,
        timeout: int = 5,
    ) -> Request:
        """Builds a Request so that the source is already populated."""
        return Request(
            source=self.name,
            target=target,
            body=body,
            timeout=timeout,
        )

    def generate_event(self, topic: str, body: str) -> Event:
        """Builds an Event so that the source is already populated."""
        return Event(source=self.name, topic=topic, body=body)

    def respond(self, request: Request, message: str) -> None:
        response = Response(
            source=self.name,
            requestor=request.source,
            body=message,
            request_id=request.id,
        )
        self._tx_queue.put(response, block=False)

    def _register(self):
        """Register with the broker."""
        timeout: int = 2
        register = Register(source=self.name)
        if response := self._sync_send(register, timeout):
            if response.type == MessageType.ACK:
                self.registered = True
                logger.success(f"{self.name} | Registered with broker: {response.body}")
            else:
                logger.error(f"{self.name} | Failed to register with broker: {response.body}")
                raise ClientException("Failed to register with broker")

    def _sync_send(self, message: Ping | Register | Request | Subscribe, timeout: int) -> Response | None:
        """Synchronous send. Waits for response."""
        future = self._executor.submit(self._sync_send_check, message)
        response: Response | None = None
        try:
            response = future.result(timeout=timeout)
            logger.success(f"{self.name} | Synchronous send successful: {message.id}")
        except Exception as e:
            logger.error(f"{self.name} | Failed to register: {e}")
            raise e
        else:
            return response
        finally:
            # Cancel the future to avoid resource leaks
            future.cancel()

    def _sync_send_check(self, message: Message) -> Response:
        self._tx_queue.put(message, block=False)
        while True:
            if message.id in self.responses:
                return self.responses.pop(message.id)

    def __listen(self):
        """Listen for messages from the broker."""
        while not self._stop.is_set():
            try:
                text = self._socket.recv(flags=NOBLOCK)
            except Again:
                continue
            if not text:
                continue
            text = text.decode("utf-8")
            message_type, model = text.split(" ", 1)
            message = self.__cast_model(message_type, model)
            self._rx_queue.put(message, block=False)
            log = f"\n# {self.name} | RX: {message_type}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.debug(log)

    def __cast_model(self, message_type: str, model: str) -> Message:
        if message_type == "RESPONSE":
            return Response.model_validate_json(model)
        elif message_type == "PONG":
            return Pong.model_validate_json(model)
        elif message_type == "EVENT":
            return Event.model_validate_json(model)
        elif message_type == "PING":
            return Ping.model_validate_json(model)
        elif message_type == "REQUEST":
            return Request.model_validate_json(model)
        elif message_type == "REGISTER":
            return Register.model_validate_json(model)
        elif message_type == "SUBSCRIBE":
            return Subscribe.model_validate_json(model)
        elif message_type == "ACK":
            return ACK.model_validate_json(model)
        else:
            raise Exception(f"Client does not support message type: {type}")

    def __handle(self):
        """Handle incoming messages."""
        while not self._stop.is_set():
            if self._rx_queue.empty():
                continue
            message = self._rx_queue.get(block=False)
            assert isinstance(message, Message)
            if message.type == MessageType.PONG:
                assert isinstance(message, Pong)
                self.responses[message.request_id] = message
            elif message.type == MessageType.EVENT:
                assert isinstance(message, Event)
                if message.topic in self._topics:
                    self._topics[message.topic].put(message, block=False)
            elif message.type == MessageType.PING:
                assert isinstance(message, Ping)
                pong = self._generate_pong(message)
                self._tx_queue.put(pong, block=False)
            elif message.type == MessageType.REQUEST:
                assert isinstance(message, Request)
                self.requests.put(message, block=False)
            elif message.type == MessageType.RESPONSE:
                assert isinstance(message, Response)
                self.responses[message.request_id] = message
            elif message.type == MessageType.ACK:
                assert isinstance(message, Response)
                self.responses[message.request_id] = message
            else:
                raise Exception(f"Client does not support message type: {message.type}")

    def _generate_pong(self, ping: Ping) -> Pong:
        """Generate a PONG message from a PING message."""
        return Pong(
            source=self.name,
            requestor=ping.source,
            request_id=ping.id,
        )

    def __send(self):
        """Send messages to the broker."""
        while not self._stop.is_set():
            if self._tx_queue.empty():
                continue
            message = self._tx_queue.get(block=False)
            assert isinstance(message, Message)
            frame = f"{message.type.value} {message.model_dump_json()}"
            self._socket.send_string(frame)
            log = f"\n# {self.name} | TX: {message.type.value}\n"
            log += f"{message.model_dump_json(indent=2)}"
            logger.debug(log)
