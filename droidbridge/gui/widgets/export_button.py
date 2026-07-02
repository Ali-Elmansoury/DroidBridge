# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from droidbridge.reports.generators import to_csv, to_html, to_json, to_txt

_RENDERERS = {"txt": to_txt, "csv": to_csv, "html": to_html, "json": to_json}
_FILTER = "Text (*.txt);;CSV (*.csv);;HTML (*.html);;JSON (*.json)"
_FILTER_FMTS = {
    "Text (*.txt)": "txt",
    "CSV (*.csv)": "csv",
    "HTML (*.html)": "html",
    "JSON (*.json)": "json",
}
_FMT_EXT = {"txt": ".txt", "csv": ".csv", "html": ".html", "json": ".json"}


def export_report(parent, dialog_title, default_name, report):
    """Prompt for a save path, render `report` by selected filter, write it, show outcome dialog."""
    path, selected_filter = QFileDialog.getSaveFileName(parent, dialog_title, default_name, _FILTER)
    if not path:
        return
    fmt = _FILTER_FMTS.get(selected_filter, "txt")
    # Qt doesn't update the typed filename when the user changes the filter dropdown,
    # so correct the extension ourselves to match what was actually selected.
    p = Path(path)
    if p.suffix.lower() != _FMT_EXT[fmt]:
        path = str(p.with_suffix(_FMT_EXT[fmt]))
    try:
        content = _RENDERERS[fmt](report)
        Path(path).write_text(content, encoding="utf-8")
        QMessageBox.information(parent, "Export Complete", f"Exported to {path}.")
    except OSError as exc:
        QMessageBox.critical(parent, "Export Failed", str(exc))
