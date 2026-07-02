# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
"""Plain-Python Reports GUI operations (sub-phase 6.5 part 3) — no Qt imports.

Wraps the same logic as `droidbridge.cli.main`'s `report generate` command:
13 report types, 4 output formats, built on the generic Report model in
`droidbridge.reports.generators`.
"""

from datetime import datetime
from pathlib import Path

from droidbridge.gui import backup_ops
from droidbridge.modules import backup_manager as backup_module
from droidbridge.modules import search as search_module
from droidbridge.modules import storage as storage_module
from droidbridge.modules import transfer as transfer_module
from droidbridge.modules import whatsapp as whatsapp_module
from droidbridge.reports import backup_reports
from droidbridge.reports import storage_reports
from droidbridge.reports import whatsapp_reports
from droidbridge.reports.generators import Report, to_csv, to_html, to_json, to_txt
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


def _build_backup_verification(profile_name):
    profile = backup_module.get_profile(backup_module.DEFAULT_PROFILES_PATH, profile_name)
    if profile is None:
        raise ValueError(f"Error: profile {profile_name!r} not found.")

    history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    record = backup_module.last_backup(history, profile_name)
    if record is None:
        raise ValueError(f"No backups recorded for profile {profile_name!r}. Run `backup run --profile {profile_name}` first.")

    actual_files, actual_bytes = backup_module.measure_destination(record.destination)
    result = transfer_module.VerificationResult(
        expected_files=record.file_count, expected_bytes=record.total_bytes,
        actual_files=actual_files, actual_bytes=actual_bytes,
    )
    return backup_reports.build_backup_verification_report(profile_name, result)


def _select_installs(installs, app):
    if app == "all":
        return installs
    package = "com.whatsapp" if app == "whatsapp" else "com.whatsapp.w4b"
    return [install for install in installs if install.package == package]


def _scan_media_files(client, serial, installs):
    media_files = []
    for install in installs:
        media_files.extend(whatsapp_module.scan_media(client, serial, install))
    return media_files


def _build_whatsapp_media_files(client, serial, app):
    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)
    if not installs:
        raise ValueError("No WhatsApp or WhatsApp Business installation found on this device.")
    return _scan_media_files(client, serial, installs)


def _build_full_report(client, serial, app, top_n):
    sections = []

    overview = storage_module.get_storage_overview(client, serial)
    storage_reports.record_storage_snapshot(overview, path=storage_reports.DEFAULT_TREND_PATH)
    sections.extend(storage_reports.build_storage_overview_report(overview).sections)

    apps = storage_module.get_app_storage(client, serial)
    sections.extend(storage_reports.build_top_apps_report(apps, top=top_n).sections)

    history = storage_reports.load_storage_history(storage_reports.DEFAULT_TREND_PATH)
    if len(history) >= 2:
        sections.extend(storage_reports.build_storage_trend_report(history).sections)

    large_files = storage_module.find_large_files(client, serial, threshold=search_module.LARGE_FILE_THRESHOLD)
    sections.extend(storage_reports.build_large_files_report(large_files).sections)

    installs = whatsapp_module.detect_installs(client, serial)
    installs = _select_installs(installs, app)
    if installs:
        media_files = _scan_media_files(client, serial, installs)
        sections.extend(whatsapp_reports.build_media_inventory_report(media_files).sections)
        sections.extend(whatsapp_reports.build_file_type_breakdown_report(media_files).sections)
        sections.extend(whatsapp_reports.build_section_breakdown_report(media_files).sections)
        sections.extend(whatsapp_reports.build_documents_categorization_report(media_files).sections)

    backup_history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
    if backup_history:
        sections.extend(backup_reports.build_backup_history_report(backup_history).sections)

    return Report(title="DroidBridge Full Report", sections=sections)


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
    elif report_type == "backup-history":
        history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
        if profile:
            history = [r for r in history if r.profile == profile]
        report = backup_reports.build_backup_history_report(history)
    elif report_type == "backup-summary":
        if not profile:
            raise ValueError("Error: --profile is required for --type backup-summary.")
        history = backup_module.load_history(backup_module.DEFAULT_HISTORY_PATH)
        record = backup_module.last_backup(history, profile)
        if record is None:
            raise ValueError(f"No backups recorded for profile {profile!r}.")
        report = backup_reports.build_backup_summary_report(record)
    elif report_type == "backup-verification":
        if not profile:
            raise ValueError("Error: --profile is required for --type backup-verification.")
        report = _build_backup_verification(profile)
    elif report_type == "whatsapp-inventory":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_media_inventory_report(media_files)
    elif report_type == "whatsapp-cutoff":
        if not cutoff:
            raise ValueError("Error: --cutoff is required for --type whatsapp-cutoff.")
        try:
            cutoff_date = datetime.strptime(cutoff, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Error: invalid --cutoff date {cutoff!r}, expected YYYY-MM-DD.")
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_cutoff_comparison_report(media_files, cutoff_date)
    elif report_type == "whatsapp-filetypes":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_file_type_breakdown_report(media_files)
    elif report_type == "whatsapp-sections":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_section_breakdown_report(media_files)
    elif report_type == "whatsapp-documents":
        media_files = _build_whatsapp_media_files(client, serial, app)
        report = whatsapp_reports.build_documents_categorization_report(media_files)
    elif report_type == "full":
        report = _build_full_report(client, serial, app, top_n)
    else:
        raise ValueError(f"Unknown report type: {report_type!r}")

    content = _RENDERERS[report_format](report)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return {"content": content, "default_filename": f"{report_type}_{timestamp}.{report_format}"}
