"""Plain-Python Reports GUI operations (sub-phase 6.5 part 3) — no Qt imports.

Wraps the same logic as `droidbridge.cli.main`'s `report generate` command:
13 report types, 4 output formats, built on the generic Report model in
`droidbridge.reports.generators`.
"""

from datetime import datetime
from pathlib import Path

from droidbridge.gui import backup_ops
from droidbridge.modules import search as search_module
from droidbridge.modules import storage as storage_module
from droidbridge.reports import storage_reports
from droidbridge.reports.generators import to_csv, to_html, to_json, to_txt
from droidbridge.utils.format import parse_size

_RENDERERS = {"txt": to_txt, "html": to_html, "csv": to_csv, "json": to_json}

REPORT_TYPES = (
    {"id": "full", "label": "Full Report", "needs_device": True,
     "params": ("top_n", "app"), "profile_required": False},
    {"id": "storage", "label": "Storage Breakdown", "needs_device": True,
     "params": (), "profile_required": False},
    {"id": "top-apps", "label": "Top Apps by Size", "needs_device": True,
     "params": ("top_n",), "profile_required": False},
    {"id": "large-files", "label": "Large Files", "needs_device": True,
     "params": ("min_size",), "profile_required": False},
    {"id": "storage-trend", "label": "Storage Trend", "needs_device": False,
     "params": (), "profile_required": False},
    {"id": "whatsapp-inventory", "label": "WhatsApp Media Inventory", "needs_device": True,
     "params": ("app",), "profile_required": False},
    {"id": "whatsapp-cutoff", "label": "WhatsApp Pre/Post Cutoff Comparison", "needs_device": True,
     "params": ("cutoff", "app"), "profile_required": False},
    {"id": "whatsapp-filetypes", "label": "WhatsApp File Type Breakdown", "needs_device": True,
     "params": ("app",), "profile_required": False},
    {"id": "whatsapp-sections", "label": "WhatsApp Sent/Received/Private Breakdown", "needs_device": True,
     "params": ("app",), "profile_required": False},
    {"id": "whatsapp-documents", "label": "WhatsApp Documents Categorization", "needs_device": True,
     "params": ("app",), "profile_required": False},
    {"id": "backup-history", "label": "Backup History", "needs_device": False,
     "params": ("profile",), "profile_required": False},
    {"id": "backup-summary", "label": "Backup Summary", "needs_device": False,
     "params": ("profile",), "profile_required": True},
    {"id": "backup-verification", "label": "Backup Verification", "needs_device": False,
     "params": ("profile",), "profile_required": True},
)

REPORT_TYPES_BY_ID = {t["id"]: t for t in REPORT_TYPES}


def list_profile_names():
    return [p.name for p in backup_ops.list_profiles()]


def save_report(content, path):
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")


def generate_report(client, serial, report_type, report_format, top_n=20, min_size=None, cutoff=None, profile=None, app="all"):
    if report_type == "storage":
        overview = storage_module.get_storage_overview(client, serial)
        storage_reports.record_storage_snapshot(overview, path=storage_reports.DEFAULT_TREND_PATH)
        report = storage_reports.build_storage_overview_report(overview)
    elif report_type == "top-apps":
        apps = storage_module.get_app_storage(client, serial)
        report = storage_reports.build_top_apps_report(apps, top=top_n)
    elif report_type == "large-files":
        threshold = parse_size(min_size) if min_size else search_module.LARGE_FILE_THRESHOLD
        results = storage_module.find_large_files(client, serial, threshold=threshold)
        report = storage_reports.build_large_files_report(results)
    elif report_type == "storage-trend":
        history = storage_reports.load_storage_history(storage_reports.DEFAULT_TREND_PATH)
        if not history:
            raise ValueError("No storage history recorded yet. Run `report generate --type storage` first.")
        report = storage_reports.build_storage_trend_report(history)
    else:
        raise ValueError(f"Unknown report type: {report_type!r}")

    content = _RENDERERS[report_format](report)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {"content": content, "default_filename": f"{report_type}_{timestamp}.{report_format}"}
