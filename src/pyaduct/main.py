import datetime
import time
from pathlib import Path

import click
from click import Context
from loguru import logger
from rich.console import Console
from rich.table import Table

from pyaduct.certs import generate_certificates
from pyaduct.factory import BrokerFactory, PyaductFactory


@click.group()
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enables verbose mode")
@click.pass_context
def main(
    ctx: Context,
    verbose: bool,
):
    """Main command group"""
    ctx.ensure_object(dict)
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    click.echo(f"Timestamp: {timestamp}")
    if verbose:
        logger.enable("pyaduct")
    else:
        logger.disable("pyaduct")


@main.command(name="broker")
@click.pass_context
@click.argument("bus", type=click.Choice(["ipc", "tcp"]), required=True)
def broker(
    ctx: Context,
    bus: str,
):
    """Broker bus type (ipc or tcp)"""
    _ = ctx
    click.echo(bus)

    broker = BrokerFactory().generate_ipc_broker()
    broker.start()
    time.sleep(1)
    broker.stop()


@main.command(name="certs")
@click.pass_context
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
)
def certs(ctx: Context, directory: Path):
    """Broker type (ipc or tcp)"""
    _ = ctx
    directory = Path(directory).absolute()
    click.echo(directory)
    cert_path = generate_certificates(directory)
    click.echo(f"Cert Path: {cert_path}")


@main.command(name="demo")
@click.pass_context
def demo(ctx: Context):
    """Broker bus type (ipc or tcp)"""
    console = Console()
    table = Table(title="Demo", show_lines=True)
    table.add_column("Client", justify="center", style="cyan", no_wrap=True)
    table.add_column("Topic", justify="center", style="magenta")
    table.add_column("Event", justify="center", style="green")
    table.add_column("Response", justify="center", style="red")
    table.add_column("Status", justify="center", style="yellow")
    table.add_column("Time", justify="center", style="blue")
    table.add_row("Client 1", "test_topic", "hello world", "ok", "success", "0.1s")
    console.print(table)
    _ = ctx
    broker, client_1, client_2 = PyaductFactory().generate_ipc_nodes()
    with console.status("Starting nodes..."):
        broker.start()
        client_1.start()
        client_2.start()
    test_topic_queue = client_1.subscribe("test_topic")
    console.print("Client 1 subscribed to test_topic")
    event = client_2.generate_event("test_topic", "hello world")
    console.print(f"Client 2 generated event: {event}")
    client_2.publish(event)
    event = test_topic_queue.get(timeout=2)
    console.print(f"Client 1 received event: {event}")
    if client_1.ping("client_2"):
        console.print("Client 1 pinged Client 2 successfully")
    with console.status("Shutting down nodes..."):
        client_1.stop()
        client_2.stop()
        broker.stop()
    console.print("All nodes stopped successfully; exiting.")
    request = client_1.generate_request("client_2", "example body")
    console.print(f"Client 1 generated request: {request}")
    response = client_1.request(request, timeout=5)
    if response:
        console.print(f"Client 1 received response: {response}")
    else:
        console.print("Client 1 did not receive a response")
