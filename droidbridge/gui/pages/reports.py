from PyQt6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from droidbridge.gui import reports_ops

_FORMAT_LABELS = ["TXT", "HTML", "CSV", "JSON"]
_FORMAT_VALUES = ["txt", "html", "csv", "json"]

_SAVE_FILTERS = {
    "txt": "Text Files (*.txt)",
    "html": "HTML Files (*.html)",
    "csv": "CSV Files (*.csv)",
    "json": "JSON Files (*.json)",
}


class ReportsPage(QWidget):
    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel
        self._current_report = None
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        row = QHBoxLayout()
        row.addWidget(QLabel("Report type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([t["label"] for t in reports_ops.REPORT_TYPES])
        self.type_combo.setToolTip("Choose which report to generate.")
        row.addWidget(self.type_combo)
        row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(_FORMAT_LABELS)
        self.format_combo.setToolTip("Output format for the generated report.")
        row.addWidget(self.format_combo)
        self.generate_button = QPushButton("Generate")
        self.generate_button.setToolTip("Generate the selected report using the current parameters.")
        row.addWidget(self.generate_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setToolTip("Preview of the generated report.")
        layout.addWidget(self.preview_text)

        save_row = QHBoxLayout()
        self.save_button = QPushButton("Save As…")
        self.save_button.setToolTip("Save the generated report to a file on your computer.")
        self.save_button.setEnabled(False)
        save_row.addWidget(self.save_button)
        save_row.addStretch()
        layout.addLayout(save_row)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect(self):
        self.generate_button.clicked.connect(self._on_generate)
        self.save_button.clicked.connect(self._on_save)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.reportGenerated.connect(self._on_report_generated)

    def _current_type(self):
        return reports_ops.REPORT_TYPES[self.type_combo.currentIndex()]

    def _on_generate(self):
        type_id = self._current_type()["id"]
        report_format = _FORMAT_VALUES[self.format_combo.currentIndex()]
        self.save_button.setEnabled(False)
        self.viewmodel.generate(type_id, report_format)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.generate_button.setEnabled(not busy)

    def _on_report_generated(self, payload):
        self._current_report = payload
        if payload["format"] == "html":
            self.preview_text.setHtml(payload["content"])
        else:
            self.preview_text.setPlainText(payload["content"])
        self.save_button.setEnabled(True)

    def _on_save(self):
        if self._current_report is None:
            return
        name_filter = _SAVE_FILTERS[self._current_report["format"]]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", self._current_report["default_filename"], name_filter,
        )
        if path:
            self.viewmodel.save(self._current_report["content"], path)
