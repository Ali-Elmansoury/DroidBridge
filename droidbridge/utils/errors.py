# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Human-readable translations for ADB and device errors."""

import re

_PATTERNS = [
    # Connection / auth
    (r"device unauthorized",
     "Phone not authorized — check your phone and tap 'Allow' on the USB debugging prompt."),
    (r"no devices/emulators found|no device",
     "No device found — make sure your phone is connected and USB Debugging is enabled."),
    (r"more than one device",
     "Multiple devices connected — use --serial to specify which one."),
    (r"device offline",
     "Device is offline — try unplugging and reconnecting the USB cable."),
    (r"device not found|device '.*' not found",
     "Device disconnected — reconnect the USB cable and try again."),
    (r"connection refused",
     "Cannot reach ADB server — try unplugging and reconnecting your phone."),
    (r"closed|broken pipe",
     "Connection lost mid-operation — the device may have disconnected."),
    (r"adb command timed out",
     "Operation timed out — the device took too long to respond. Try again."),

    # Filesystem
    (r"permission denied",
     "Permission denied — this path is restricted on your device."),
    (r"read-only file system",
     "Cannot write here — the destination is read-only on your device."),
    (r"no such file or directory",
     "Path not found on the device."),
    (r"not a directory",
     "Expected a folder but found a file at that path."),
    (r"file exists",
     "A file already exists at that destination."),
    (r"no space left",
     "Not enough storage space on the device."),

    # Transfer
    (r"remote object does not exist",
     "File no longer exists on the device."),
    (r"failed to copy",
     "File transfer failed — check the path and that the device is still connected."),
    (r"protocol fault",
     "ADB protocol error — unplug and reconnect the device, then try again."),

    # ADB binary / setup
    (r"adb.*not found|cannot find adb",
     "ADB binary not found — this is a DroidBridge installation issue. Please reinstall."),
    (r"find: bad arg|find:.*unknown.*option",
     "A shell command is not supported on this device. Please report this to the developer."),
]

# Compile once at import time
_COMPILED = [(re.compile(p, re.IGNORECASE), msg) for p, msg in _PATTERNS]


def friendly_error(exc: Exception) -> str:
    """Return a human-readable error message for *exc*.

    Checks the exception's string representation against known ADB/device
    error patterns. Falls back to the raw exception text if nothing matches,
    so no information is lost.
    """
    raw = str(exc)
    for pattern, message in _COMPILED:
        if pattern.search(raw):
            return message
    return raw
