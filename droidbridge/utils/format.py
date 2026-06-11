"""Shared formatting helpers (sizes, etc.)."""

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


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
