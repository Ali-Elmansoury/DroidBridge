# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Storage reports (spec §9.2): breakdown, top apps, large files, storage trend."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from droidbridge.modules.storage import top_space_consumers
from droidbridge.reports.generators import Report, ReportSection
from droidbridge.utils.format import format_bytes

DEFAULT_DATA_DIR = Path.home() / ".droidbridge"
DEFAULT_TREND_PATH = DEFAULT_DATA_DIR / "storage_history.json"


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class StorageSnapshot:
    """A single point-in-time storage measurement, for trend comparison."""

    timestamp: str
    total_kb: int
    used_kb: int
    free_kb: int


def build_storage_overview_report(overview):
    """Phone storage breakdown report (spec §9.2)."""
    percent_used = 0 if overview.total_kb == 0 else round(overview.used_kb / overview.total_kb * 100)
    sections = [
        ReportSection(
            title="Overview",
            text=(
                f"Total: {format_bytes(overview.total_kb * 1024)}, "
                f"Used: {format_bytes(overview.used_kb * 1024)} ({percent_used}%), "
                f"Free: {format_bytes(overview.free_kb * 1024)}"
            ),
        ),
    ]
    category_rows = [[category, format_bytes(size)] for category, size in overview.categories.items() if size]
    if category_rows:
        sections.append(
            ReportSection(title="Categories", headers=["Category", "Size"], rows=category_rows)
        )
    return Report(title="Storage Breakdown Report", sections=sections)


def build_top_apps_report(apps, top=20):
    """Top apps by size report (spec §9.2)."""
    rows = [
        [
            app.package,
            format_bytes(app.apk_size),
            format_bytes(app.data_size),
            format_bytes(app.cache_size),
            format_bytes(app.total_size),
        ]
        for app in top_space_consumers(apps, top)
    ]
    section = ReportSection(
        title=f"Top {len(rows)} Apps by Size",
        headers=["Package", "APK", "Data", "Cache", "Total"],
        rows=rows,
    )
    return Report(title="Top Apps by Size Report", sections=[section])


def build_large_files_report(results):
    """Large files report (spec §9.2 / §5.4)."""
    rows = [[r.path, format_bytes(r.size), r.mtime.isoformat()] for r in results]
    section = ReportSection(title="Large Files", headers=["Path", "Size", "Modified"], rows=rows)
    return Report(title="Large Files Report", sections=[section])


def record_storage_snapshot(overview, path=DEFAULT_TREND_PATH, timestamp=None):
    """Append a `StorageSnapshot` for `overview` to the trend history at `path`."""
    snapshot = StorageSnapshot(
        timestamp=timestamp or _now_iso(),
        total_kb=overview.total_kb,
        used_kb=overview.used_kb,
        free_kb=overview.free_kb,
    )
    history = load_storage_history(path)
    history.append(snapshot)

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in history], f, indent=2)
    return snapshot


def load_storage_history(path=DEFAULT_TREND_PATH):
    """Load all recorded `StorageSnapshot`s from `path`, oldest first."""
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [StorageSnapshot(**item) for item in data]


def build_storage_trend_report(history):
    """Storage trend report: used/free space across recorded sessions, with deltas (spec §9.2)."""
    rows = []
    previous = None
    for snapshot in history:
        if previous is None:
            change = ""
        else:
            delta_kb = snapshot.used_kb - previous.used_kb
            sign = "+" if delta_kb >= 0 else "-"
            change = f"{sign}{format_bytes(abs(delta_kb) * 1024)}"
        rows.append(
            [
                snapshot.timestamp,
                format_bytes(snapshot.used_kb * 1024),
                format_bytes(snapshot.free_kb * 1024),
                change,
            ]
        )
        previous = snapshot
    section = ReportSection(title="Storage Over Time", headers=["Date", "Used", "Free", "Change"], rows=rows)
    return Report(title="Storage Trend Report", sections=[section])
