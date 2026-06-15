"""Plain-Python GUI device operations (Phase 6.1) — no Qt imports.

These wrap the same droidbridge.modules.device functions the CLI uses, so the GUI never
duplicates business logic. They raise exceptions (AdbError, DeviceSelectionError) instead
of calling click.echo/sys.exit, so they can run inside a Worker on a background thread.
"""

from droidbridge.core.adb import AdbClient
from droidbridge.modules import device as device_module


def connect():
    """Build an AdbClient, ensure the adb server is running, and resolve the ready device.

    Returns (client, serial, model, health_messages).
    Raises AdbError (e.g. adb binary not found) or DeviceSelectionError (no/ambiguous
    ready device) on failure.
    """
    client = AdbClient()
    device_module.ensure_adb_server_running(client)
    _, messages = device_module.check_connection_health(client)

    serial = device_module.resolve_ready_device(client)

    ready = device_module.get_ready_devices(client)
    model = next(d.model for d in ready if d.serial == serial)

    return client, serial, model, messages


def refresh_info(client, serial):
    """Return a DeviceInfo for `serial` (thin wrapper around device_module.get_device_info)."""
    return device_module.get_device_info(client, serial)


def is_device_ready(client, serial):
    """Return True if `serial` is currently in adb's ready ('device') list (spec §1.1)."""
    return any(d.serial == serial for d in device_module.get_ready_devices(client))
