"""Platform abstraction: picks the right SleepInhibitor for the current OS."""

import platform

from droidbridge.core.platform import linux, macos, windows

_INHIBITORS = {
    "linux": linux.SleepInhibitor,
    "windows": windows.SleepInhibitor,
    "darwin": macos.SleepInhibitor,
}


def get_sleep_inhibitor(reason="DroidBridge transfer in progress", system=None):
    """Return a SleepInhibitor for `system` (default: the current OS)."""
    system = (system or platform.system()).lower()
    cls = _INHIBITORS.get(system, linux.SleepInhibitor)
    return cls(reason)
