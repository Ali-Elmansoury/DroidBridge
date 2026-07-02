# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Module 1 - Device Manager: detection, info, storage breakdown, connection health."""

import re
from dataclasses import dataclass
from typing import Optional

from droidbridge.core.adb import AdbError

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


class DeviceSelectionError(Exception):
    """Raised by resolve_ready_device when no device, multiple devices with no serial
    given, or an unknown/not-ready serial is selected."""


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
class UsbModeInfo:
    """Current USB function mode, parsed from `getprop sys.usb.state` (spec §1.4)."""

    functions: list
    mtp_enabled: bool
    guidance: Optional[str] = None


USB_SPEED_LOOKUP = {
    # raw value (lowercased) -> (usb_type, estimated_speed)
    "1.5": ("USB 1.0 (Low Speed)", "~0.1 MB/s"),
    "12": ("USB 1.1 (Full Speed)", "~1 MB/s"),
    "480": ("USB 2.0 (High Speed)", "~30-40 MB/s"),
    "5000": ("USB 3.0 / 3.1 Gen 1 (SuperSpeed)", "~150-300 MB/s"),
    "10000": ("USB 3.1 / 3.2 Gen 2 (SuperSpeed+)", "~300-600 MB/s"),
    "low": ("USB 1.0 (Low Speed)", "~0.1 MB/s"),
    "full": ("USB 1.1 (Full Speed)", "~1 MB/s"),
    "high": ("USB 2.0 (High Speed)", "~30-40 MB/s"),
    "super": ("USB 3.0 / 3.1 Gen 1 (SuperSpeed)", "~150-300 MB/s"),
    "super-speed-plus": ("USB 3.1 / 3.2 Gen 2 (SuperSpeed+)", "~300-600 MB/s"),
}

# Candidate sysfs paths exposing the gadget-side USB negotiated speed.
# If none work on a given device, falls back to "Unknown" (no error).
USB_SPEED_PATHS = (
    "/sys/class/android_usb/android0/speed",
    "/sys/class/android_usb/android0/current_speed",
)


@dataclass
class UsbSpeedInfo:
    """Best-effort USB connection type/speed estimate (spec §1.2)."""

    raw: Optional[str] = None
    usb_type: str = "Unknown"
    estimated_speed: str = "Unknown"


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
    usb_speed: Optional[UsbSpeedInfo] = None
    usb_mode: Optional[UsbModeInfo] = None


def list_devices(client):
    """Return all devices known to adb, in any state."""
    return client.devices()


def get_ready_devices(client):
    """Return only devices in the 'device' (ready) state."""
    return [d for d in client.devices() if d.is_ready]


def resolve_ready_device(client, serial=None):
    """Return the serial of the device to use.

    Raises DeviceSelectionError (with a human-readable guidance message) if there are no
    ready devices, if `serial` is None and multiple devices are ready, or if `serial` does
    not match a ready device.

    If adb sees device(s) but none are ready (e.g. "unauthorized" - USB debugging is
    enabled but the "Allow USB debugging?" prompt hasn't been accepted on the phone yet,
    or "offline"), the error message uses that device's specific connection guidance
    rather than the generic "no device" message, which would otherwise wrongly tell the
    user to enable USB debugging when it's already enabled.
    """
    devices = client.devices()
    ready = [d for d in devices if d.is_ready]
    if not ready:
        if not devices:
            raise DeviceSelectionError(connection_guidance("no device"))
        lines = [f"{d.serial}: {connection_guidance(d.state)}" for d in devices]
        raise DeviceSelectionError("\n".join(lines))

    ready_serials = [d.serial for d in ready]
    if serial is None:
        if len(ready) > 1:
            lines = ["Multiple devices connected. Specify one with --serial:"]
            lines.extend(f"  {d.serial}  ({d.model})" for d in ready)
            raise DeviceSelectionError("\n".join(lines))
        return ready_serials[0]

    if serial not in ready_serials:
        raise DeviceSelectionError(f"Error: device '{serial}' not found or not ready.")

    return serial


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


def get_usb_mode_info(client, serial):
    """Return the current USB function mode (spec §1.4)."""
    raw = client.shell(serial, ["getprop", "sys.usb.state"]).strip()
    functions = [f for f in raw.split(",") if f]
    mtp_enabled = "mtp" in functions
    guidance = None
    if not mtp_enabled:
        guidance = (
            "USB mode is not set to File Transfer (MTP). For best compatibility, "
            "pull down the USB notification on your phone and select "
            "'File Transfer' / 'MTP'."
        )
    return UsbModeInfo(functions=functions, mtp_enabled=mtp_enabled, guidance=guidance)


def get_usb_speed_info(client, serial):
    """Best-effort USB connection type/speed estimate (spec §1.2)."""
    for path in USB_SPEED_PATHS:
        try:
            output = client.shell(serial, ["cat", path]).strip().lower()
        except AdbError:
            continue
        if not output:
            continue
        usb_type, estimated = USB_SPEED_LOOKUP.get(output, (None, None))
        if usb_type:
            return UsbSpeedInfo(raw=output, usb_type=usb_type, estimated_speed=estimated)
        return UsbSpeedInfo(raw=output)
    return UsbSpeedInfo()


def get_device_info(client, serial):
    """Gather model, manufacturer, Android version, battery, storage, and USB info."""
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
        usb_speed=get_usb_speed_info(client, serial),
        usb_mode=get_usb_mode_info(client, serial),
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


def wait_for_device(client, serial=None, timeout=None):
    """Block until adb reports a device is connected (spec §1.1)."""
    client.wait_for_device(serial=serial, timeout=timeout)
