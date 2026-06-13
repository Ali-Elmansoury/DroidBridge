"""Module 2 - File Browser: directory listing, sorting, filtering."""

import re
import shlex
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Optional

_LS_LINE_RE = re.compile(
    r"^(?P<type>[bcdlpsD-])(?P<perms>[r\-wxsStT]{9})\s+"
    r"(?P<links>\d+)\s+"
    r"(?P<owner>\S+)\s+"
    r"(?P<group>\S+)\s+"
    r"(?P<size>\d+)\s+"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<time>\d{2}:\d{2})\s+"
    r"(?P<name>.+)$"
)

SORT_KEYS = ("name", "size", "date", "type")


@dataclass
class FileEntry:
    """A single file or directory entry from a directory listing."""

    name: str
    path: str
    is_dir: bool
    is_symlink: bool
    size: int
    mtime: datetime
    link_target: str = ""

    @property
    def extension(self):
        if self.is_dir:
            return ""
        return PurePosixPath(self.name).suffix.lstrip(".").lower()


def _join_path(dir_path, name):
    if dir_path == "/":
        return f"/{name}"
    return f"{dir_path.rstrip('/')}/{name}"


def list_directory(client, serial, path):
    """List the contents of `path` on the device.

    Runs `ls -la <path>/` (trailing slash forces listing of directory
    contents even when `path` is itself a symlink to a directory, e.g.
    `/sdcard`).
    """
    dir_path = path if path.endswith("/") else f"{path}/"
    output = client.shell(serial, f"ls -la {shlex.quote(dir_path)}")

    entries = []
    for line in output.splitlines():
        line = line.rstrip()
        if not line or line.startswith("total "):
            continue

        match = _LS_LINE_RE.match(line)
        if not match:
            continue

        name = match.group("name")
        link_target = ""
        is_symlink = match.group("type") == "l"
        if is_symlink and " -> " in name:
            name, _, link_target = name.partition(" -> ")

        entries.append(
            FileEntry(
                name=name,
                path=_join_path(dir_path, name),
                is_dir=match.group("type") == "d",
                is_symlink=is_symlink,
                size=int(match.group("size")),
                mtime=datetime.strptime(
                    f"{match.group('date')} {match.group('time')}", "%Y-%m-%d %H:%M"
                ),
                link_target=link_target,
            )
        )

    return entries


def make_directory(client, serial, path):
    """Create `path` (and any missing parent directories) on the device."""
    client.shell(serial, f"mkdir -p {shlex.quote(path)}")


def sort_entries(entries, by="name", reverse=False):
    """Return entries sorted by 'name', 'size', 'date', or 'type'.

    'type' sorts directories first, then files by extension and name.
    """
    if by == "name":
        key = lambda e: e.name.lower()
    elif by == "size":
        key = lambda e: e.size
    elif by == "date":
        key = lambda e: e.mtime
    elif by == "type":
        key = lambda e: (0 if e.is_dir else 1, e.extension, e.name.lower())
    else:
        raise ValueError(f"Unknown sort key {by!r}; expected one of {SORT_KEYS}")

    return sorted(entries, key=key, reverse=reverse)


def filter_entries(
    entries,
    extensions=None,
    min_size=None,
    max_size=None,
    after=None,
    before=None,
    include_hidden=True,
    dirs_pass_extension_filter=True,
):
    """Filter entries by extension, size range, date range, and hidden status.

    Directories always pass the `extensions` filter (so navigation still
    works), but are still subject to the other filters. Pass
    `dirs_pass_extension_filter=False` to hide directories too whenever an
    extension filter is active.
    """
    result = []
    for entry in entries:
        if not include_hidden and entry.name.startswith("."):
            continue
        if entry.is_dir:
            if extensions is not None and not dirs_pass_extension_filter:
                continue
            result.append(entry)
            continue
        if extensions is not None and entry.extension not in extensions:
            continue
        if min_size is not None and entry.size < min_size:
            continue
        if max_size is not None and entry.size > max_size:
            continue
        if after is not None and entry.mtime < after:
            continue
        if before is not None and entry.mtime > before:
            continue
        result.append(entry)

    return result
