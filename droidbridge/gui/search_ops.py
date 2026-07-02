# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Plain-Python GUI search operations (Phase 6.2) — no Qt imports.

These wrap droidbridge.modules.search the same way the CLI's `files search` command
does, so the GUI never duplicates business logic.
"""

from droidbridge.modules import search as search_module


def build_search_kwargs(root, name, extensions, min_size, max_size, after, before, preset, name_regex=None):
    """Merge form fields with a preset, matching `files search` CLI semantics.

    Returns (root_path, kwargs) ready for
    search_files(client, serial, root_path, **kwargs).
    """
    if name and name_regex:
        raise ValueError("name and name_regex are mutually exclusive")

    kwargs = {}
    root_path = root or None

    if preset:
        preset_root, preset_kwargs = search_module.preset_filters(preset)
        kwargs.update(preset_kwargs)
        if root_path is None:
            root_path = preset_root

    if root_path is None:
        root_path = search_module.DEFAULT_ROOT

    if name:
        if "*" not in name and "?" not in name:
            name = f"*{name}*"
        kwargs["name_pattern"] = name

    if name_regex:
        kwargs["name_regex"] = name_regex

    if extensions:
        kwargs["extensions"] = extensions

    if min_size is not None:
        kwargs["min_size"] = min_size

    if max_size is not None:
        kwargs["max_size"] = max_size

    if after is not None:
        kwargs["after"] = after

    if before is not None:
        kwargs["before"] = before

    return root_path, kwargs


def run_search(client, serial, root, name=None, extensions=None, min_size=None,
                max_size=None, after=None, before=None, preset=None, sort_by="path",
                reverse=False, name_regex=None):
    """build_search_kwargs(...) -> search_files() -> sort_results()."""
    root_path, kwargs = build_search_kwargs(
        root, name, extensions, min_size, max_size, after, before, preset,
        name_regex=name_regex,
    )
    results = search_module.search_files(client, serial, root_path, **kwargs)
    return search_module.sort_results(results, by=sort_by, reverse=reverse)
