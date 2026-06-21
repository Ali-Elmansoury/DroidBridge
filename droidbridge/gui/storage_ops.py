"""Plain-Python Storage Analyzer GUI operations (sub-phase 6.5 part 1) — no Qt imports."""

from droidbridge.modules import storage as storage_module
from droidbridge.utils import format as format_utils

_CATEGORY_LABELS = (
    ("apps", "Apps"),
    ("app_data", "App Data"),
    ("app_cache", "App Cache"),
    ("photos", "Photos"),
    ("videos", "Videos"),
    ("audio", "Audio"),
    ("downloads", "Downloads"),
    ("system", "System"),
    ("other", "Other"),
)


def get_overview(client, serial):
    overview = storage_module.get_storage_overview(client, serial)
    total_bytes = overview.total_kb * 1024
    used_bytes = overview.used_kb * 1024
    free_bytes = overview.free_kb * 1024
    percent = 0 if total_bytes <= 0 else round(used_bytes / total_bytes * 100)
    categories = [
        {"label": label, "size_str": format_utils.format_bytes(overview.categories[key])}
        for key, label in _CATEGORY_LABELS
        if overview.categories.get(key, 0) > 0
    ]
    return {
        "total_str": format_utils.format_bytes(total_bytes),
        "used_str": format_utils.format_bytes(used_bytes),
        "free_str": format_utils.format_bytes(free_bytes),
        "percent": percent,
        "categories": categories,
    }


def get_apps(client, serial, filter_kind=None):
    apps = storage_module.get_app_storage(client, serial)
    if filter_kind == "system":
        apps = [a for a in apps if a.is_system]
    elif filter_kind == "user":
        apps = [a for a in apps if not a.is_system]
    apps = storage_module.top_space_consumers(apps, n=len(apps))
    return [
        {
            "package": a.package,
            "total_size_str": format_utils.format_bytes(a.total_size),
            "apk_size_str": format_utils.format_bytes(a.apk_size),
            "data_size_str": format_utils.format_bytes(a.data_size),
            "cache_size_str": format_utils.format_bytes(a.cache_size),
            "kind": "system" if a.is_system else "user",
        }
        for a in apps
    ]


def get_media(client, serial, root, before=None):
    breakdown = storage_module.analyze_media(client, serial, root, before=before)
    categories = [
        {"type": media_type, "count": count, "size_str": format_utils.format_bytes(size)}
        for media_type, (count, size) in breakdown.categories.items()
    ]
    largest_files = [
        {"size_str": format_utils.format_bytes(r.size), "path": r.path}
        for r in breakdown.largest_files
    ]
    groups = sorted(breakdown.duplicates, key=lambda g: g[0].size * (len(g) - 1), reverse=True)
    duplicate_groups = [
        {
            "name": group[0].name,
            "size_str": format_utils.format_bytes(group[0].size),
            "count": len(group),
            "paths": [r.path for r in group],
        }
        for group in groups[:10]
    ]
    return {
        "total_count": breakdown.total_count,
        "total_size_str": format_utils.format_bytes(breakdown.total_size),
        "categories": categories,
        "largest_files": largest_files,
        "duplicate_groups": duplicate_groups,
        "duplicate_overflow": max(0, len(groups) - 10),
    }


def get_large_files(client, serial, root, threshold=None):
    if threshold is None:
        results = storage_module.find_large_files(client, serial, root)
    else:
        results = storage_module.find_large_files(client, serial, root, threshold=threshold)
    return [
        {
            "size_str": format_utils.format_bytes(r.size),
            "path": r.path,
            "modified_str": r.mtime.strftime("%Y-%m-%d %H:%M"),
        }
        for r in results
    ]


def get_cleanup_suggestions(client, serial):
    suggestions = storage_module.suggest_cleanup(client, serial)
    rows = [
        {
            "title": s.title,
            "description": s.description,
            "estimated_bytes_str": format_utils.format_bytes(s.estimated_bytes),
            "item_count": len(s.items),
            "items": list(s.items[:10]),
            "item_overflow": max(0, len(s.items) - 10),
        }
        for s in suggestions
    ]
    total_bytes = sum(s.estimated_bytes for s in suggestions)
    return {"suggestions": rows, "total_str": format_utils.format_bytes(total_bytes)}
