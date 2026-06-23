from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QProgressBar, QPushButton, QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from droidbridge.gui import reports_ops

_FORMAT_LABELS = ["TXT", "HTML", "CSV", "JSON"]
_FORMAT_VALUES = ["txt", "html", "csv", "json"]

_APP_LABELS = ["WhatsApp", "WhatsApp Business", "Both"]
_APP_VALUES = ["whatsapp", "business", "all"]

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
        self._on_type_changed()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Report type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems([t["label"] for t in reports_ops.REPORT_TYPES])
        self.type_combo.setToolTip("Choose which report to generate.")
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        layout.addLayout(type_row)

        params_row = QHBoxLayout()
        self.top_spin_label = QLabel("Top N:")
        self.top_spin = QSpinBox()
        self.top_spin.setRange(1, 9999)
        self.top_spin.setValue(20)
        self.top_spin.setToolTip("How many top entries to include in the report.")
        params_row.addWidget(self.top_spin_label)
        params_row.addWidget(self.top_spin)

        self.min_size_label = QLabel("Minimum size:")
        self.min_size_edit = QLineEdit()
        self.min_size_edit.setPlaceholderText("e.g. 50MB")
        self.min_size_edit.setToolTip("Only include files at least this size. Leave blank for the default threshold.")
        params_row.addWidget(self.min_size_label)
        params_row.addWidget(self.min_size_edit)

        self.cutoff_label = QLabel("Cutoff date:")
        self.cutoff_date_edit = QDateEdit(QDate.currentDate())
        self.cutoff_date_edit.setCalendarPopup(True)
        self.cutoff_date_edit.setToolTip("Compare WhatsApp media created before and after this date.")
        params_row.addWidget(self.cutoff_label)
        params_row.addWidget(self.cutoff_date_edit)

        self.app_label = QLabel("App:")
        self.app_combo = QComboBox()
        self.app_combo.addItems(_APP_LABELS)
        self.app_combo.setToolTip("Which WhatsApp installation(s) to include.")
        params_row.addWidget(self.app_label)
        params_row.addWidget(self.app_combo)

        self.profile_label = QLabel("Profile:")
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip("Backup profile to report on.")
        params_row.addWidget(self.profile_label)
        params_row.addWidget(self.profile_combo)

        params_row.addStretch()
        layout.addLayout(params_row)

        self._param_widgets = {
            "top_n": (self.top_spin_label, self.top_spin),
            "min_size": (self.min_size_label, self.min_size_edit),
            "cutoff": (self.cutoff_label, self.cutoff_date_edit),
            "app": (self.app_label, self.app_combo),
            "profile": (self.profile_label, self.profile_combo),
        }

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(_FORMAT_LABELS)
        self.format_combo.setToolTip("Output format for the generated report.")
        action_row.addWidget(self.format_combo)
        self.generate_button = QPushButton("Generate")
        self.generate_button.setToolTip("Generate the selected report using the current parameters.")
        action_row.addWidget(self.generate_button)
        action_row.addStretch()
        layout.addLayout(action_row)

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
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self.generate_button.clicked.connect(self._on_generate)
        self.save_button.clicked.connect(self._on_save)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.reportGenerated.connect(self._on_report_generated)

    def _current_type(self):
        return reports_ops.REPORT_TYPES[self.type_combo.currentIndex()]

    def _on_type_changed(self):
        type_def = self._current_type()
        params = type_def["params"]
        for key, (label, widget) in self._param_widgets.items():
            visible = key in params
            label.setVisible(visible)
            widget.setVisible(visible)
        if "profile" in params:
            self._refresh_profile_combo()

    def _refresh_profile_combo(self):
        type_def = self._current_type()
        names = reports_ops.list_profile_names()
        self.profile_combo.clear()
        if not type_def["profile_required"]:
            self.profile_combo.addItem("(all profiles)")
        self.profile_combo.addItems(names)

    def showEvent(self, event):
        super().showEvent(event)
        if "profile" in self._current_type()["params"]:
            self._refresh_profile_combo()

    def _collect_params(self, type_def):
        params = {}
        keys = type_def["params"]
        if "top_n" in keys:
            params["top_n"] = self.top_spin.value()
        if "min_size" in keys:
            text = self.min_size_edit.text().strip()
            if text:
                params["min_size"] = text
        if "cutoff" in keys:
            params["cutoff"] = self.cutoff_date_edit.date().toString("yyyy-MM-dd")
        if "app" in keys:
            params["app"] = _APP_VALUES[self.app_combo.currentIndex()]
        if "profile" in keys:
            if type_def["profile_required"] and self.profile_combo.count() == 0:
                self.viewmodel.logMessage.emit(
                    f"A backup profile is required for the {type_def['label']} report. "
                    "Create one first in the Backup Manager.",
                    "WARNING",
                )
                return None
            text = self.profile_combo.currentText()
            params["profile"] = None if text == "(all profiles)" else text
        return params

    def _on_generate(self):
        type_def = self._current_type()
        report_format = _FORMAT_VALUES[self.format_combo.currentIndex()]
        params = self._collect_params(type_def)
        if params is None:
            return
        self.save_button.setEnabled(False)
        self.viewmodel.generate(type_def["id"], report_format, **params)

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
