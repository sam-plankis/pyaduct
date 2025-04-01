import os
import shutil
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator, Union

import pytest
from loguru import logger
from zmq import DEALER, ROUTER, Context
from zmq.auth import create_certificates, load_certificate
from zmq.auth.thread import ThreadAuthenticator

from pyaduct import Broker, Client
from pyaduct.store import InmemMessageStore

logger.enable("pyaduct")


def thread_watcher(stop: threading.Event):
    while not stop.is_set():
        debug = "\n# Thread Debug #\n"
        debug += f"Timestamp: {time.time()}\n"
        debug += f"Thread count: {threading.active_count()}\n"
        for thread in threading.enumerate():
            if thread is threading.main_thread():
                continue
            if thread.is_alive():
                debug += f"Thread name: {thread.name}, alive: {thread.is_alive()}\n"
        logger.debug(debug)
        time.sleep(1)


@pytest.fixture
def ctx() -> Generator[Context, None, None]:
    """A fixture that provides a ZMQ context for testing."""
    context = Context()
    yield context
    context.destroy()


@pytest.fixture
def certs() -> Generator[tuple[Path, Path], None, None]:
    """A fixture that provides a key pair for testing."""
    temp_dir = TemporaryDirectory()
    temp_path = Path(temp_dir.name)
    generate_certificates(temp_path)
    keys_dir = os.path.join(temp_path, "certificates")
    _ = keys_dir
    public_keys_dir = Path(os.path.join(temp_path, "public_keys"))
    secret_keys_dir = Path(os.path.join(temp_path, "private_keys"))
    yield (public_keys_dir, secret_keys_dir)
    temp_dir.cleanup()


def generate_certificates(base_dir: Union[str, os.PathLike]) -> None:
    """Generate client and server CURVE certificate files"""
    keys_dir = os.path.join(base_dir, "certificates")
    public_keys_dir = os.path.join(base_dir, "public_keys")
    secret_keys_dir = os.path.join(base_dir, "private_keys")
    for d in [keys_dir, public_keys_dir, secret_keys_dir]:
        if os.path.exists(d):
            shutil.rmtree(d)
        os.mkdir(d)
    create_certificates(keys_dir, "server")
    create_certificates(keys_dir, "client")
    for key_file in os.listdir(keys_dir):
        if key_file.endswith(".key"):
            shutil.move(
                os.path.join(keys_dir, key_file),
                os.path.join(public_keys_dir, "."),
            )
    for key_file in os.listdir(keys_dir):
        if key_file.endswith(".key_secret"):
            shutil.move(
                os.path.join(keys_dir, key_file),
                os.path.join(secret_keys_dir, "."),
            )


@pytest.fixture
def ipc_broker():
    """A fixture that provides an IPC broker for testing."""
    store = InmemMessageStore()
    address = "ipc://pyaduct"
    context = Context()
    socket = context.socket(ROUTER)
    socket.bind(address)
    broker = Broker(socket, store=store, latency=(0.3, 0.7))
    broker.start()
    yield broker
    broker.stop()


def generate_ipc_client(ctx: Context, client_name: str) -> Client:
    """Generate an IPC client with the given name."""
    assert isinstance(client_name, str), "Client name must be a string"
    socket = ctx.socket(DEALER)
    address = "ipc://pyaduct"
    socket.connect(address)
    store = InmemMessageStore()
    client = Client(socket, store=store, name=client_name)
    return client


@pytest.fixture
def ipc_client_1(ctx, ipc_broker):
    """A fixture that provides an IPC client for testing."""
    _ = ipc_broker  # to ensure broker is started before client
    client = generate_ipc_client(ctx, "client_1")
    client.start()
    yield client
    client.stop()


@pytest.fixture
def ipc_client_2(ctx, ipc_broker):
    """A fixture that provides an IPC client for testing."""
    _ = ipc_broker  # to ensure broker is started before client
    client = generate_ipc_client(ctx, "client_2")
    client.start()
    yield client
    client.stop()


@pytest.fixture
def tcp_broker(certs, ctx):
    """A fixture that provides an IPC broker for testing."""
    assert isinstance(ctx, Context)
    public_keys_dir, secret_keys_dir = certs
    logger.debug(f"Public keys dir: {public_keys_dir}, Secret keys dir: {secret_keys_dir}")
    auth = ThreadAuthenticator(ctx)
    auth.start()
    auth.allow("127.0.0.1")
    auth.configure_curve(domain="*", location=public_keys_dir)
    server = ctx.socket(ROUTER)
    server_secret_file = os.path.join(secret_keys_dir, "server.key_secret")
    server_public, server_secret = load_certificate(server_secret_file)
    server.curve_secretkey = server_secret
    server.curve_publickey = server_public
    server.curve_server = True
    address = "tcp://*:5555"
    server.bind(address)
    broker = Broker(server)
    broker.start()
    yield broker
    broker.stop()


def generate_tcp_client(certs: tuple[Path, Path], ctx: Context, client_name: str) -> Client:
    """Generate a TCP client with the given name."""
    assert isinstance(client_name, str), "Client name must be a string"
    socket = ctx.socket(DEALER)
    public_keys_dir, secret_keys_dir = certs
    client_secret_file = os.path.join(secret_keys_dir, "client.key_secret")
    client_public, client_secret = load_certificate(client_secret_file)
    socket.curve_secretkey = client_secret
    socket.curve_publickey = client_public
    server_public_file = os.path.join(public_keys_dir, "server.key")
    server_public, _ = load_certificate(server_public_file)
    socket.curve_serverkey = server_public
    address = "tcp://127.0.0.1:5555"
    socket.connect(address)
    client = Client(socket, name=client_name)
    client.name = client_name
    return client


@pytest.fixture(scope="function")
def tcp_client_1(tcp_broker, certs, ctx):
    """A fixture that provides a TCP client for testing."""
    _ = tcp_broker  # to ensure broker is started before client
    client = generate_tcp_client(certs, ctx, "client_1")
    client.start()
    yield client
    client.stop()


@pytest.fixture
def tcp_client_2(tcp_broker, certs, ctx):
    """A fixture that provides a TCP client for testing."""
    _ = tcp_broker  # to ensure broker is started before client
    client = generate_tcp_client(certs, ctx, "client_2")
    client.start()
    yield client
    client.stop()
