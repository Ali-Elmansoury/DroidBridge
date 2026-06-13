"""Plain-Python GUI file-browser operations (Phase 6.2) — no Qt imports.

These wrap the same droidbridge.modules.files functions the CLI's `files browse`
command uses, so the GUI never duplicates business logic.
"""

from pathlib import PurePosixPath

from droidbridge.modules import files as files_module
from droidbridge.modules import search as search_module

QUICK_JUMP_PATHS = {
    "Root": "/sdcard",
    "DCIM": "/sdcard/DCIM",
    "Downloads": "/sdcard/Download",
    "Pictures": "/sdcard/Pictures",
    "WhatsApp Media": search_module.WHATSAPP_MEDIA_PATH,
}


def list_path(client, serial, path, sort_by="name", reverse=False, show_hidden=False, extensions=None):
    """Return the sorted, filtered directory listing for `path`, mirroring `files browse`."""
    entries = files_module.list_directory(client, serial, path)
    entries = files_module.filter_entries(entries, extensions=extensions, include_hidden=show_hidden)
    return files_module.sort_entries(entries, by=sort_by, reverse=reverse)


def parent_path(path):
    """Return the parent directory of `path` ('/sdcard/DCIM' -> '/sdcard'); '/' stays '/'."""
    if path == "/":
        return "/"
    return str(PurePosixPath(path).parent)


def join_path(dir_path, name):
    """Join `dir_path` and `name` ('/sdcard', 'New Folder') -> '/sdcard/New Folder'."""
    if dir_path == "/":
        return f"/{name}"
    return f"{dir_path.rstrip('/')}/{name}"


def make_directory(client, serial, path):
    """Create `path` (and any missing parent directories) on the device."""
    files_module.make_directory(client, serial, path)
