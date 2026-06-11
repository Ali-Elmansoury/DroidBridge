"""Module 1 - Device Manager: detection, info, storage breakdown, connection health."""

import re
from dataclasses import dataclass
from typing import Optional

BATTERY_STATUS_NAMES = {
    "1": "unknown",
    "2": "charging",
    "3": "discharging",
    "4": "not charging",
    "5": "full",
}

CONNECTION_GUIDANCE = {
    "device": "Device connected and ready.",
    "unauthorized": (
        "Device is unauthorized. Check your phone for an 'Allow USB debugging?' "
        "prompt and tap Allow (optionally check 'Always allow from this computer')."
    ),
    "offline": (
        "Device is offline. Try unplugging and reconnecting the USB cable, or "
        "restart the ADB server."
    ),
    "no device": (
        "No device detected. Enable Developer Options and USB debugging on your "
        "phone (Settings > About phone > tap Build number 7 times, then "
        "Settings > Developer options > USB debugging), then reconnect the USB cable."
    ),
}


@dataclass
class StorageInfo:
    """Storage breakdown for a mount point, in KB."""

    total_kb: int
    used_kb: int
    free_kb: int

    @property
    def used_percent(self):
        if self.total_kb == 0:
            return 0.0
        return round(self.used_kb / self.total_kb * 100, 1)


@dataclass
class DeviceInfo:
    """Aggregated device information for Module 1."""

    serial: str
    model: str = ""
    manufacturer: str = ""
    android_version: str = ""
    sdk_version: str = ""
    build_number: str = ""
    battery_level: Optional[int] = None
    battery_status: str = ""
    storage: Optional[StorageInfo] = None


def list_devices(client):
    """Return all devices known to adb, in any state."""
    return client.devices()


def get_ready_devices(client):
    """Return only devices in the 'device' (ready) state."""
    return [d for d in client.devices() if d.is_ready]


def connection_guidance(state):
    """Return a human-readable guidance message for a connection state."""
    return CONNECTION_GUIDANCE.get(state, f"Device is in state '{state}'.")


def _getprop(client, serial, prop):
    return client.shell(serial, ["getprop", prop]).strip()


def get_storage_breakdown(client, serial, mount_point="/sdcard"):
    """Parse `df <mount_point>` into a StorageInfo (sizes in KB)."""
    output = client.shell(serial, ["df", mount_point])
    lines = [line for line in output.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError(f"Unexpected 'df {mount_point}' output: {output!r}")

    parts = lines[-1].split()
    if len(parts) < 4:
        raise ValueError(f"Unexpected 'df {mount_point}' output line: {lines[-1]!r}")

    try:
        total_kb, used_kb, free_kb = int(parts[1]), int(parts[2]), int(parts[3])
    except ValueError as exc:
        raise ValueError(f"Unexpected 'df {mount_point}' output line: {lines[-1]!r}") from exc

    return StorageInfo(total_kb=total_kb, used_kb=used_kb, free_kb=free_kb)


def get_battery_info(client, serial):
    """Return (level_percent, status_name) parsed from `dumpsys battery`."""
    output = client.shell(serial, ["dumpsys", "battery"])

    level_match = re.search(r"level:\s*(\d+)", output)
    status_match = re.search(r"status:\s*(\d+)", output)

    level = int(level_match.group(1)) if level_match else None
    status = BATTERY_STATUS_NAMES.get(
        status_match.group(1) if status_match else None, "unknown"
    )
    return level, status


def get_device_info(client, serial):
    """Gather model, manufacturer, Android version, battery, and storage info."""
    battery_level, battery_status = get_battery_info(client, serial)
    return DeviceInfo(
        serial=serial,
        model=_getprop(client, serial, "ro.product.model"),
        manufacturer=_getprop(client, serial, "ro.product.manufacturer"),
        android_version=_getprop(client, serial, "ro.build.version.release"),
        sdk_version=_getprop(client, serial, "ro.build.version.sdk"),
        build_number=_getprop(client, serial, "ro.build.display.id"),
        battery_level=battery_level,
        battery_status=battery_status,
        storage=get_storage_breakdown(client, serial),
    )


def check_connection_health(client):
    """Return (devices, guidance_messages) describing the ADB connection state."""
    devices = client.devices()
    if not devices:
        return devices, [connection_guidance("no device")]

    messages = [f"{d.serial}: {connection_guidance(d.state)}" for d in devices]
    return devices, messages


def ensure_adb_server_running(client):
    """Make sure the adb server is running, starting it if needed."""
    client.start_server()


def restart_adb_server(client):
    """Restart the adb server (e.g. to recover from an offline device)."""
    client.restart_server()
