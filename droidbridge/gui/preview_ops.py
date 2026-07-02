# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Plain-Python GUI image-preview operations (Phase 6.2) — no Qt imports.

Fetches and caches a local copy of a previewable file from the device so the Files
page can show it in a QPixmap without re-pulling on every selection.
"""

import hashlib
import os
from pathlib import PurePosixPath

PREVIEWABLE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "bmp"}  # Qt's natively-supported formats
MAX_PREVIEW_SIZE = 25 * 1024 * 1024  # 25 MB

DEFAULT_CACHE_DIR = os.path.expanduser("~/.droidbridge/preview_cache")


class PreviewTooLargeError(Exception):
    """Raised by fetch_preview() when entry.size > MAX_PREVIEW_SIZE."""


def is_previewable(entry):
    """True if `entry` is a file with an extension in PREVIEWABLE_EXTENSIONS."""
    return not entry.is_dir and entry.extension in PREVIEWABLE_EXTENSIONS


def cache_path(cache_dir, entry):
    """Return the local cache file path for `entry`.

    Keyed by a hash of (entry.path, entry.size, entry.mtime), so changed files
    re-fetch but unchanged files reuse the cached copy.
    """
    key = f"{entry.path}|{entry.size}|{entry.mtime.isoformat()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    suffix = PurePosixPath(entry.path).suffix
    return os.path.join(cache_dir, f"{digest}{suffix}")


def fetch_preview(client, serial, entry, cache_dir=None):
    """Return the local cache path for `entry`, pulling it via client.pull() if not cached.

    Raises PreviewTooLargeError if entry.size > MAX_PREVIEW_SIZE. Default cache_dir:
    ~/.droidbridge/preview_cache/.
    """
    if entry.size > MAX_PREVIEW_SIZE:
        raise PreviewTooLargeError(f"{entry.path} is {entry.size} bytes (max {MAX_PREVIEW_SIZE})")

    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    local_path = cache_path(cache_dir, entry)

    if not os.path.exists(local_path):
        client.pull(serial, entry.path, local_path)

    return local_path
