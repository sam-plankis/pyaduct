import datetime
from pathlib import Path

import click
from click import Context
from loguru import logger

from pyaduct.certs import generate_certificates


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
        logger.enable("actorbus")
    else:
        logger.disable("actorbus")


@main.command(name="broker")
@click.pass_context
@click.argument("bus", type=click.Choice(["ipc, tcp"]), required=True)
def broker(
    ctx: Context,
    bus: str,
):
    """Broker bus type (ipc or tcp)"""
    _ = ctx
    click.echo(bus)


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
    server, client = generate_certificates(directory)
    click.echo(f"Server certs: {server}")
    click.echo(f"Client certs: {client}")
