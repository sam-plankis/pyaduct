import datetime
import time
from pathlib import Path

import click
from click import Context
from loguru import logger
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table

from pyaduct import Client
from pyaduct.broker import Broker
from pyaduct.certs import generate_certificates
from pyaduct.factory import BrokerFactory, PyaductFactory
from pyaduct.store import IMessageStore


@click.group()
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Enables verbose mode",
)
@click.pass_context
def main(
    ctx: Context,
    verbose: bool,
):
    """Main command group"""
    ctx.ensure_object(dict)
    console = Console()
    ctx.obj["console"] = Console()
    timestamp = datetime.datetime.now(datetime.timezone.utc)
    console.print(f"Timestamp: {timestamp}")
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
    console = ctx.obj["console"]
    broker, client_1, client_2 = PyaductFactory().generate_demo_ipc_nodes()
    with Live(console=console) as live:
        spinner = Spinner("dots", text="Initializing broker and clients...")
        live.update(spinner)
        broker.start()
        client_1.start()
        client_2.start()
        test_topic_queue = client_1.subscribe("test_topic")
        live.console.print("Client 1 subscribed to test_topic")
        event = client_2.generate_event("test_topic", "hello world")
        live.console.print(f"Client 2 generated event: {event}")
        client_2.publish(event)
        event = test_topic_queue.get(timeout=4)
        live.console.print_json(event.model_dump_json())
        live.console.print(f"Client 1 received event: {event}")
        if client_1.ping("client_2"):
            live.console.print("Client 1 pinged Client 2 successfully")
        spinner = Spinner("dots", text="Shutting down...")
        live.update(spinner)
        client_1.stop()
        client_2.stop()
        broker.stop()
    console.print(generate_table(broker))
    console.print(generate_table(client_1))
    console.print(generate_table(client_2))


def generate_table(node: Broker | Client) -> Table:
    assert isinstance(node.store, IMessageStore)
    title = f"{node.name} Messages"
    table = Table(title=title)
    table.add_column("Message ID", style="cyan")
    table.add_column("Direction", style="magenta")
    table.add_column("Type", style="blue")
    table.add_column("Body", style="white")
    table.add_column("Timestamp", style="yellow")
    for message in node.store:
        direction = "TX" if message.source == node.name else "RX"
        table.add_row(
            str(message.id),
            direction,
            message.type.name,
            message.body,
            str(message.timestamp),
        )
    return table
