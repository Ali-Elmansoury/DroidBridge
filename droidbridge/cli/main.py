"""Click-based CLI entry point for DroidBridge."""

import sys

import click

from droidbridge.core.adb import AdbClient, AdbError
from droidbridge.modules import device as device_module
from droidbridge.modules import files as files_module
from droidbridge.modules import search as search_module
from droidbridge.utils.format import format_bytes, format_size_kb, parse_size


def _build_client():
    """Construct the AdbClient. Patched in tests to avoid touching real adb."""
    return AdbClient()


def _resolve_serial(client, serial):
    """Resolve a device serial, exiting with guidance if missing/ambiguous/unknown."""
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
        return ready_serials[0]

    if serial not in ready_serials:
        click.echo(f"Error: device '{serial}' not found or not ready.", err=True)
        sys.exit(1)

    return serial


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

    serial = _resolve_serial(client, serial)

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


@cli.group("files")
def files_cmd():
    """Browse and search files on the device."""


def _entry_type_char(entry):
    if entry.is_symlink:
        return "l"
    if entry.is_dir:
        return "d"
    return "-"


def _format_entry_line(entry):
    type_char = _entry_type_char(entry)
    size = format_bytes(entry.size)
    date = entry.mtime.strftime("%Y-%m-%d %H:%M")
    name = entry.name
    if entry.is_symlink and entry.link_target:
        name = f"{name} -> {entry.link_target}"
    return f"{type_char}  {size:>10}  {date}  {name}"


@files_cmd.command("browse")
@click.argument("path", default="/sdcard")
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
@click.option(
    "--sort",
    "-S",
    "sort_by",
    type=click.Choice(files_module.SORT_KEYS),
    default="name",
    help="Sort by name, size, date, or type.",
)
@click.option("--reverse", "-r", is_flag=True, help="Reverse the sort order.")
@click.option("--all", "-a", "show_hidden", is_flag=True, help="Show hidden files.")
@click.option(
    "--ext",
    "-e",
    "extensions",
    multiple=True,
    help="Only show files with this extension (repeatable).",
)
def files_browse(path, serial, sort_by, reverse, show_hidden, extensions):
    """List files at PATH on the device (default: /sdcard)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    try:
        entries = files_module.list_directory(client, serial, path)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    extensions_filter = [e.lower().lstrip(".") for e in extensions] or None
    entries = files_module.filter_entries(
        entries, extensions=extensions_filter, include_hidden=show_hidden
    )
    entries = files_module.sort_entries(entries, by=sort_by, reverse=reverse)

    if not entries:
        click.echo("(empty)")
        return

    for entry in entries:
        click.echo(_format_entry_line(entry))


def _format_result_line(result):
    size = format_bytes(result.size)
    date = result.mtime.strftime("%Y-%m-%d %H:%M")
    return f"{size:>10}  {date}  {result.path}"


PRESET_NAMES = ("whatsapp", "photos", "videos", "documents", "apks", "large", "old", "no-extension")


@files_cmd.command("search")
@click.argument("path", default=None, required=False)
@click.option(
    "--serial",
    "-s",
    default=None,
    help="Device serial number (required if multiple devices are connected).",
)
@click.option("--name", default=None, help="Filter by filename (partial match or glob pattern).")
@click.option(
    "--ext",
    "-e",
    "extensions",
    multiple=True,
    help="Only show files with this extension (repeatable).",
)
@click.option("--min-size", default=None, help="Minimum file size, e.g. 10MB.")
@click.option("--max-size", default=None, help="Maximum file size, e.g. 100MB.")
@click.option(
    "--after",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only files modified on or after this date (YYYY-MM-DD).",
)
@click.option(
    "--before",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Only files modified on or before this date (YYYY-MM-DD).",
)
@click.option(
    "--preset",
    type=click.Choice(PRESET_NAMES),
    default=None,
    help="Quick discovery preset.",
)
@click.option(
    "--sort",
    "-S",
    "sort_by",
    type=click.Choice(search_module.SORT_KEYS),
    default="path",
    help="Sort by name, size, date, or path.",
)
@click.option("--reverse", "-r", is_flag=True, help="Reverse the sort order.")
def files_search(path, serial, name, extensions, min_size, max_size, after, before, preset, sort_by, reverse):
    """Search for files on the device (default root: /sdcard)."""
    try:
        client = _build_client()
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    serial = _resolve_serial(client, serial)

    kwargs = {}
    root = path
    if preset:
        preset_root, preset_kwargs = search_module.preset_filters(preset)
        kwargs.update(preset_kwargs)
        if root is None:
            root = preset_root

    if root is None:
        root = search_module.DEFAULT_ROOT

    if name:
        if "*" not in name and "?" not in name:
            name = f"*{name}*"
        kwargs["name_pattern"] = name

    if extensions:
        kwargs["extensions"] = [e.lower().lstrip(".") for e in extensions]

    if min_size:
        kwargs["min_size"] = parse_size(min_size)

    if max_size:
        kwargs["max_size"] = parse_size(max_size)

    if after:
        kwargs["after"] = after

    if before:
        kwargs["before"] = before

    try:
        results = search_module.search_files(client, serial, root, **kwargs)
    except AdbError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    results = search_module.sort_results(results, by=sort_by, reverse=reverse)

    if not results:
        click.echo("No files found.")
        return

    for result in results:
        click.echo(_format_result_line(result))


if __name__ == "__main__":
    cli()
