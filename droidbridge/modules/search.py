"""Module 7 - Search & Discovery: recursive file search with combined filters."""

import shlex
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath

DEFAULT_ROOT = "/sdcard"
WHATSAPP_MEDIA_PATH = "/sdcard/Android/media/com.whatsapp/WhatsApp/Media"

SORT_KEYS = ("name", "size", "date", "path")

PRESET_EXTENSIONS = {
    "photos": ["jpg", "jpeg", "png", "heic", "raw"],
    "videos": ["mp4", "mov", "mkv"],
    "documents": ["pdf", "docx", "pptx", "xlsx"],
    "apks": ["apk"],
}

PRESET_NAMES = ("whatsapp", "photos", "videos", "documents", "apks", "large", "old", "no-extension")

LARGE_FILE_THRESHOLD = 50 * 1024 * 1024
OLD_FILE_AGE = timedelta(days=365)


@dataclass
class SearchResult:
    """A single file matched by a search."""

    path: str
    size: int
    mtime: datetime

    @property
    def name(self):
        return PurePosixPath(self.path).name

    @property
    def extension(self):
        return PurePosixPath(self.path).suffix.lstrip(".").lower()


def _build_find_command(root_path, name_pattern=None):
    # -L follows symlinks (e.g. /sdcard -> /storage/self/primary), without
    # which a recursive search from /sdcard returns nothing.
    cmd = f"find -L {shlex.quote(root_path)} -type f"
    if name_pattern:
        cmd += f" -iname {shlex.quote(name_pattern)}"
    cmd += r" -printf '%p\t%s\t%T@\n'"
    return cmd


def _parse_find_output(output):
    results = []
    for line in output.splitlines():
        if not line.strip():
            continue
        path, size, mtime = line.split("\t")
        results.append(
            SearchResult(path=path, size=int(size), mtime=datetime.fromtimestamp(float(mtime)))
        )
    return results


def filter_results(results, extensions=None, min_size=None, max_size=None, after=None, before=None):
    """Filter search results by extension, size range, and/or date range."""
    filtered = []
    for result in results:
        if extensions is not None and result.extension not in extensions:
            continue
        if min_size is not None and result.size < min_size:
            continue
        if max_size is not None and result.size > max_size:
            continue
        if after is not None and result.mtime < after:
            continue
        if before is not None and result.mtime > before:
            continue
        filtered.append(result)

    return filtered


def search_files(
    client,
    serial,
    root_path=DEFAULT_ROOT,
    name_pattern=None,
    extensions=None,
    min_size=None,
    max_size=None,
    after=None,
    before=None,
):
    """Recursively search `root_path` for files matching the given filters."""
    cmd = _build_find_command(root_path, name_pattern)
    # No timeout: a recursive search of /sdcard can take well over 30s.
    output = client.shell(serial, cmd, timeout=None)
    results = _parse_find_output(output)
    return filter_results(
        results, extensions=extensions, min_size=min_size, max_size=max_size, after=after, before=before
    )


def sort_results(results, by="path", reverse=False):
    """Sort search results by 'name', 'size', 'date', or 'path'."""
    if by == "name":
        key = lambda r: r.name.lower()
    elif by == "size":
        key = lambda r: r.size
    elif by == "date":
        key = lambda r: r.mtime
    elif by == "path":
        key = lambda r: r.path
    else:
        raise ValueError(f"Unknown sort key {by!r}; expected one of {SORT_KEYS}")

    return sorted(results, key=key, reverse=reverse)


def preset_filters(preset, now=None):
    """Return (root_path_override, search_files kwargs) for a quick-discovery preset.

    `root_path_override` is None unless the preset implies a specific search
    root (e.g. the WhatsApp media folder).
    """
    if preset == "whatsapp":
        return WHATSAPP_MEDIA_PATH, {}

    if preset in PRESET_EXTENSIONS:
        return None, {"extensions": PRESET_EXTENSIONS[preset]}

    if preset == "large":
        return None, {"min_size": LARGE_FILE_THRESHOLD}

    if preset == "old":
        now = now or datetime.now()
        return None, {"before": now - OLD_FILE_AGE}

    if preset == "no-extension":
        return None, {"extensions": [""]}

    raise ValueError(f"Unknown preset: {preset!r}")
