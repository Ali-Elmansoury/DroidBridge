"""Plain-Python GUI delete/rename operations (Phase 6.3) — no Qt imports.

These wrap the same droidbridge.modules.files functions the CLI's `files
rename` and `files delete` commands use, so the GUI never duplicates business
logic.
"""

from droidbridge.modules import files as files_module


def rename_path(client, serial, old_path, new_path):
    """Rename/move `old_path` to `new_path` on the device."""
    files_module.rename_path(client, serial, old_path, new_path)


def build_delete_plan(client, serial, paths):
    """Return a DeletePlan describing what deleting `paths` would remove."""
    return files_module.build_delete_plan(client, serial, paths)


def delete_paths(client, serial, paths):
    """Permanently delete `paths` from the device."""
    files_module.delete_paths(client, serial, paths)


def verify_deletion(client, serial, paths):
    """Return a DeleteVerification describing which of `paths` still exist."""
    return files_module.verify_deletion(client, serial, paths)
