"""Plain-Python Reports GUI operations (sub-phase 6.5 part 3) — no Qt imports.

Wraps the same logic as `droidbridge.cli.main`'s `report generate` command:
13 report types, 4 output formats, built on the generic Report model in
`droidbridge.reports.generators`.
"""

from pathlib import Path

from droidbridge.gui import backup_ops

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
