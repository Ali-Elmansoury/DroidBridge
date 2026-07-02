# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Module 5 - Storage Analyzer: full breakdown, app storage, media, large files, cleanup suggestions."""

import json
import re
import shlex
from dataclasses import dataclass
from datetime import datetime

from droidbridge.modules import device as device_module
from droidbridge.modules import search as search_module
from droidbridge.utils.format import format_bytes

# Maps `dumpsys diskstats` Estimate labels to StorageOverview.categories keys,
# in the order they're displayed (spec §5.1: Apps, Images, Videos, Audio,
# Documents, Downloads, System).
DISKSTATS_CATEGORIES = (
    ("App Size", "apps"),
    ("App Data Size", "app_data"),
    ("App Cache Size", "app_cache"),
    ("Photos Size", "photos"),
    ("Videos Size", "videos"),
    ("Audio Size", "audio"),
    ("Downloads Size", "downloads"),
    ("System Size", "system"),
    ("Other Size", "other"),
)


@dataclass
class StorageOverview:
    """Storage totals (from `df`) plus an Android category breakdown (from `dumpsys diskstats`)."""

    total_kb: int
    used_kb: int
    free_kb: int
    categories: dict


def parse_diskstats_categories(output):
    """Parse the category 'Estimate' lines of `dumpsys diskstats` output (bytes)."""
    categories = {}
    for label, key in DISKSTATS_CATEGORIES:
        match = re.search(rf"^{re.escape(label)}: (\d+)", output, re.MULTILINE)
        if match:
            categories[key] = int(match.group(1))
    return categories


def get_storage_overview(client, serial):
    """Combine `df /sdcard` totals with the `dumpsys diskstats` category breakdown."""
    storage_info = device_module.get_storage_breakdown(client, serial)
    diskstats_output = client.shell(serial, ["dumpsys", "diskstats"])
    return StorageOverview(
        total_kb=storage_info.total_kb,
        used_kb=storage_info.used_kb,
        free_kb=storage_info.free_kb,
        categories=parse_diskstats_categories(diskstats_output),
    )


@dataclass
class AppStorageInfo:
    """Per-app storage breakdown (spec §5.2)."""

    package: str
    apk_size: int
    data_size: int
    cache_size: int
    is_system: bool

    @property
    def total_size(self):
        return self.apk_size + self.data_size + self.cache_size


def _diskstats_array(output, label):
    match = re.search(rf"^{re.escape(label)}: (\[.*\])$", output, re.MULTILINE)
    return json.loads(match.group(1)) if match else []


def parse_diskstats_apps(output):
    """Parse the per-package arrays of `dumpsys diskstats` into (package, apk, data, cache) tuples."""
    packages = _diskstats_array(output, "Package Names")
    apk_sizes = _diskstats_array(output, "App Sizes")
    data_sizes = _diskstats_array(output, "App Data Sizes")
    cache_sizes = _diskstats_array(output, "Cache Sizes")
    return list(zip(packages, apk_sizes, data_sizes, cache_sizes))


def parse_package_list(output):
    """Parse `pm list packages` output into a set of package names."""
    return {line.split(":", 1)[1] for line in output.splitlines() if line.startswith("package:")}


def get_app_storage(client, serial):
    """Return per-app storage info, flagging system apps via `pm list packages -s`."""
    diskstats_output = client.shell(serial, ["dumpsys", "diskstats"])
    system_output = client.shell(serial, ["pm", "list", "packages", "-s"])
    system_packages = parse_package_list(system_output)

    return [
        AppStorageInfo(
            package=package,
            apk_size=apk_size,
            data_size=data_size,
            cache_size=cache_size,
            is_system=package in system_packages,
        )
        for package, apk_size, data_size, cache_size in parse_diskstats_apps(diskstats_output)
    ]


def top_space_consumers(apps, n=20):
    """Return the top `n` apps by total size (APK + data + cache), descending."""
    return sorted(apps, key=lambda a: a.total_size, reverse=True)[:n]


def flag_large_cache(apps, threshold):
    """Return apps whose cache size exceeds `threshold` bytes."""
    return [a for a in apps if a.cache_size > threshold]


# Audio extensions for media analysis (spec §5.3 has no "audio" preset in
# search_module, so it's defined here).
AUDIO_EXTENSIONS = ["mp3", "m4a", "wav", "ogg", "opus", "flac", "aac", "wma"]

MEDIA_TYPE_EXTENSIONS = {
    "photos": search_module.PRESET_EXTENSIONS["photos"],
    "videos": search_module.PRESET_EXTENSIONS["videos"],
    "audio": AUDIO_EXTENSIONS,
    "documents": search_module.PRESET_EXTENSIONS["documents"],
}

ALL_MEDIA_EXTENSIONS = [ext for exts in MEDIA_TYPE_EXTENSIONS.values() for ext in exts]

DEFAULT_LARGEST_FILES = 20


@dataclass
class MediaBreakdown:
    """Result of `analyze_media` (spec §5.3)."""

    categories: dict
    largest_files: list
    duplicates: list
    total_count: int
    total_size: int


def categorize_media(results):
    """Group search results into photos/videos/audio/documents -> (count, total_bytes)."""
    categories = {}
    for media_type, extensions in MEDIA_TYPE_EXTENSIONS.items():
        matching = [r for r in results if r.extension in extensions]
        categories[media_type] = (len(matching), sum(r.size for r in matching))
    return categories


def find_largest_files(results, n=DEFAULT_LARGEST_FILES):
    """Return the `n` largest files by size, descending."""
    return sorted(results, key=lambda r: r.size, reverse=True)[:n]


def find_duplicates(results):
    """Group files with the same name and size; return only groups with 2+ files."""
    groups = {}
    for result in results:
        groups.setdefault((result.name, result.size), []).append(result)
    return [group for group in groups.values() if len(group) > 1]


def analyze_media(client, serial, root=search_module.DEFAULT_ROOT, before=None):
    """Scan `root` for photo/video/audio/document files and build a MediaBreakdown."""
    results = search_module.search_files(
        client, serial, root, extensions=ALL_MEDIA_EXTENSIONS, before=before
    )
    return MediaBreakdown(
        categories=categorize_media(results),
        largest_files=find_largest_files(results),
        duplicates=find_duplicates(results),
        total_count=len(results),
        total_size=sum(r.size for r in results),
    )


def find_large_files(client, serial, root=search_module.DEFAULT_ROOT, threshold=search_module.LARGE_FILE_THRESHOLD):
    """Find files at or above `threshold` bytes (default 50MB), sorted by size descending (spec §5.4)."""
    results = search_module.search_files(client, serial, root, min_size=threshold)
    return search_module.sort_results(results, by="size", reverse=True)


# Cleanup suggestions (spec §5.5)

DOWNLOAD_DIR = "/sdcard/Download"

CACHE_SUGGESTION_THRESHOLD = 50 * 1024 * 1024  # 50MB

# Well-known thumbnail cache locations on Android (legacy + modern media stores).
THUMBNAIL_DIRS = (
    "/sdcard/DCIM/.thumbnails",
    "/sdcard/Pictures/.thumbnails",
    "/sdcard/Movies/.thumbnails",
)


@dataclass
class CleanupSuggestion:
    """A single cleanup suggestion (spec §5.5): what to clean and how much space it could free."""

    title: str
    description: str
    estimated_bytes: int
    items: list


def find_thumbnail_caches(client, serial):
    """Return (path, size_bytes) for each well-known thumbnail cache directory that exists."""
    found = []
    for path in THUMBNAIL_DIRS:
        quoted = shlex.quote(path)
        exists = client.shell(serial, f"[ -d {quoted} ] && echo 1 || echo 0").strip()
        if exists != "1":
            continue
        size_kb = int(client.shell(serial, f"du -sk {quoted}").split()[0])
        found.append((path, size_kb * 1024))
    return found


def suggest_cleanup(client, serial, apps=None):
    """Build a list of CleanupSuggestions: large app caches, leftover APK
    installers in Downloads, old log files, and thumbnail caches."""
    suggestions = []

    if apps is None:
        apps = get_app_storage(client, serial)
    large_cache_apps = flag_large_cache(apps, CACHE_SUGGESTION_THRESHOLD)
    if large_cache_apps:
        suggestions.append(
            CleanupSuggestion(
                title="Clear app caches",
                description=f"{len(large_cache_apps)} app(s) have a cache larger than {format_bytes(CACHE_SUGGESTION_THRESHOLD)}",
                estimated_bytes=sum(a.cache_size for a in large_cache_apps),
                items=[a.package for a in large_cache_apps],
            )
        )

    apk_files = search_module.search_files(client, serial, DOWNLOAD_DIR, extensions=["apk"])
    if apk_files:
        suggestions.append(
            CleanupSuggestion(
                title="APK installer files in Downloads",
                description=f"{len(apk_files)} .apk file(s) in {DOWNLOAD_DIR}",
                estimated_bytes=sum(f.size for f in apk_files),
                items=[f.path for f in apk_files],
            )
        )

    old_logs = search_module.search_files(
        client,
        serial,
        search_module.DEFAULT_ROOT,
        extensions=["log"],
        before=datetime.now() - search_module.OLD_FILE_AGE,
    )
    if old_logs:
        suggestions.append(
            CleanupSuggestion(
                title="Old log files",
                description=f"{len(old_logs)} .log file(s) older than 1 year",
                estimated_bytes=sum(f.size for f in old_logs),
                items=[f.path for f in old_logs],
            )
        )

    thumbnail_caches = find_thumbnail_caches(client, serial)
    if thumbnail_caches:
        suggestions.append(
            CleanupSuggestion(
                title="Thumbnail caches",
                description=f"{len(thumbnail_caches)} thumbnail cache director(y/ies) found",
                estimated_bytes=sum(size for _, size in thumbnail_caches),
                items=[path for path, _ in thumbnail_caches],
            )
        )

    return suggestions
