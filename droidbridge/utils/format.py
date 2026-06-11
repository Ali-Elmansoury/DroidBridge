"""Shared formatting helpers (sizes, etc.)."""

import re

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")

_SIZE_UNIT_MULTIPLIERS = {
    "b": 1,
    "k": 1024,
    "kb": 1024,
    "m": 1024 ** 2,
    "mb": 1024 ** 2,
    "g": 1024 ** 3,
    "gb": 1024 ** 3,
    "t": 1024 ** 4,
    "tb": 1024 ** 4,
}

_SIZE_RE = re.compile(r"^([\d.]+)\s*([a-zA-Z]*)$")


def format_bytes(num_bytes):
    """Return a human-readable string for a size in bytes (e.g. '1.5 GB')."""
    size = float(num_bytes)
    for unit in _UNITS:
        if size < 1024 or unit == _UNITS[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} {_UNITS[-1]}"


def format_size_kb(size_kb):
    """Return a human-readable string for a size given in KB."""
    return format_bytes(size_kb * 1024)


def parse_size(value):
    """Parse a human-readable size string (e.g. '10MB', '1.5KB', '100') into bytes."""
    match = _SIZE_RE.match(value.strip())
    if not match:
        raise ValueError(f"Invalid size: {value!r}")

    number, unit = match.groups()
    unit = unit.lower() or "b"
    if unit not in _SIZE_UNIT_MULTIPLIERS:
        raise ValueError(f"Unknown size unit {unit!r} in {value!r}")

    return int(float(number) * _SIZE_UNIT_MULTIPLIERS[unit])
