"""Click-based CLI entry point for DroidBridge."""

import sys

import click

from droidbridge.core.adb import AdbClient, AdbError
from droidbridge.modules import device as device_module
from droidbridge.utils.format import format_size_kb


def _build_client():
    """Construct the AdbClient. Patched in tests to avoid touching real adb."""
    return AdbClient()


@click.group()
def cli():
    """DroidBridge - ADB-powered Android device management tool."""


@cli.group("device")
def device_cmd():
    """Device detection, info, and connection management."""


@device_cmd.command("connect")
def device_connect():
    """Check ADB connection status and guide setup if needed."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    device_module.ensure_adb_server_running(client)
    devices, messages = device_module.check_connection_health(client)

    for message in messages:
        click.echo(message)

    if not any(d.is_ready for d in devices):
        sys.exit(1)


@device_cmd.command("info")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
def device_info(serial):
    """Show device info and storage breakdown."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    ready = device_module.get_ready_devices(client)
    if not ready:
        click.echo(device_module.connection_guidance("no device"), err=True)
        sys.exit(1)

    ready_serials = [d.serial for d in ready]
    if serial is None:
        if len(ready) > 1:
            click.echo("Multiple devices connected. Specify one with --serial:", err=True)
            for d in ready:
                click.echo(f"  {d.serial}  ({d.model})", err=True)
            sys.exit(1)
        serial = ready_serials[0]
    elif serial not in ready_serials:
        click.echo(f"Error: device '{serial}' not found or not ready.", err=True)
        sys.exit(1)

    info = device_module.get_device_info(client, serial)

    click.echo(f"Serial:        {info.serial}")
    click.echo(f"Model:         {info.model}")
    click.echo(f"Manufacturer:  {info.manufacturer}")
    click.echo(f"Android:       {info.android_version} (SDK {info.sdk_version})")
    click.echo(f"Build:         {info.build_number}")
    click.echo(f"Battery:       {info.battery_level}% ({info.battery_status})")
    click.echo("Storage:")
    click.echo(f"  Total:  {format_size_kb(info.storage.total_kb)}")
    click.echo(
        f"  Used:   {format_size_kb(info.storage.used_kb)} "
        f"({info.storage.used_percent}%)"
    )
    click.echo(f"  Free:   {format_size_kb(info.storage.free_kb)}")


if __name__ == "__main__":
    cli()
