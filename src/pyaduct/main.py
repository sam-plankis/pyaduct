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
    table = Table(title="Broker Messages")
    table.add_column("Message ID", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Body", style="white")
    table.add_column("Timestamp", style="yellow")
    assert broker.store
    for message in broker.store.messages:
        table.add_row(
            str(message.id),
            message.source,
            message.type.name,
            message.body,
            str(message.timestamp),
        )
    console.print(table)

