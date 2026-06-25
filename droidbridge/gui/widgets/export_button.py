from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from droidbridge.reports.generators import to_csv, to_html, to_json, to_txt

_RENDERERS = {"txt": to_txt, "csv": to_csv, "html": to_html, "json": to_json}
_FILTER = "Text (*.txt);;CSV (*.csv);;HTML (*.html);;JSON (*.json)"


def _fmt_from_path(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in (".html", ".htm"):
        return "html"
    if suffix == ".json":
        return "json"
    return "txt"


def export_report(parent, dialog_title, default_name, report):
    """Prompt for a save path, render `report` by extension, write it, show outcome dialog."""
    path, _ = QFileDialog.getSaveFileName(parent, dialog_title, default_name, _FILTER)
    if not path:
        return
    try:
        content = _RENDERERS[_fmt_from_path(path)](report)
        Path(path).write_text(content, encoding="utf-8")
        QMessageBox.information(parent, "Export Complete", f"Exported to {path}.")
    except OSError as exc:
        QMessageBox.critical(parent, "Export Failed", str(exc))
