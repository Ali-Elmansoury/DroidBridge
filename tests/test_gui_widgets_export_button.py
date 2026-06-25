import csv
import json
from pathlib import Path
from unittest.mock import patch

from droidbridge.reports.generators import Report, ReportSection
from droidbridge.gui.widgets.export_button import export_report

_REPORT = Report(
    title="Test Report",
    sections=[ReportSection(title="Data", headers=["A", "B"], rows=[["x", "y"]])],
)


class TestExportReport:
    def test_txt_extension_writes_txt_format(self, tmp_path):
        out = str(tmp_path / "out.txt")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                export_report(None, "Title", "out.txt", _REPORT)
        content = Path(out).read_text()
        assert "Test Report" in content
        assert "== Data ==" in content
        assert "x\ty" in content

    def test_csv_extension_writes_csv_format(self, tmp_path):
        out = str(tmp_path / "out.csv")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                export_report(None, "Title", "out.txt", _REPORT)
        with open(out, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        assert rows[0] == ["Test Report"]
        assert ["A", "B"] in rows
        assert ["x", "y"] in rows

    def test_html_extension_writes_html_format(self, tmp_path):
        out = str(tmp_path / "out.html")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                export_report(None, "Title", "out.txt", _REPORT)
        content = Path(out).read_text()
        assert "<html" in content
        assert "Test Report" in content

    def test_json_extension_writes_json_format(self, tmp_path):
        out = str(tmp_path / "out.json")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(out, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.information"):
                export_report(None, "Title", "out.txt", _REPORT)
        data = json.loads(Path(out).read_text())
        assert data["title"] == "Test Report"

    def test_cancelled_dialog_writes_nothing(self, tmp_path):
        out = str(tmp_path / "out.txt")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=("", "")):
            export_report(None, "Title", "out.txt", _REPORT)
        assert not Path(out).exists()

    def test_oserror_triggers_critical_not_information(self, tmp_path):
        bad_path = str(tmp_path / "no_dir" / "out.txt")
        with patch("droidbridge.gui.widgets.export_button.QFileDialog.getSaveFileName", return_value=(bad_path, "")):
            with patch("droidbridge.gui.widgets.export_button.QMessageBox.critical") as mock_crit:
                with patch("droidbridge.gui.widgets.export_button.QMessageBox.information") as mock_info:
                    export_report(None, "Title", "out.txt", _REPORT)
        mock_crit.assert_called_once()
        mock_info.assert_not_called()
        assert "Export Failed" in mock_crit.call_args[0][1]
