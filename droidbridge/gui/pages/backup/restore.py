from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from droidbridge.gui.viewmodels.backup.restore import RestoreViewModel

_CONFLICT_OPTIONS = ["(profile default)", "skip", "overwrite", "rename"]
_RESULT_COLUMNS = ["Source", "Done", "Total", "Failed", "Verified"]


class RestorePanel(QWidget):
    def __init__(self, context, get_profile, parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self.viewmodel = RestoreViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Sources to restore (unchecked = skip):"))
        self.sources_list = QListWidget()
        layout.addWidget(self.sources_list)

        date_row = QHBoxLayout()
        self.date_filter_checkbox = QCheckBox("Filter by date")
        date_row.addWidget(self.date_filter_checkbox)
        date_row.addWidget(QLabel("After:"))
        self.after_date_edit = QDateEdit(QDate.currentDate())
        self.after_date_edit.setCalendarPopup(True)
        date_row.addWidget(self.after_date_edit)
        date_row.addWidget(QLabel("Before:"))
        self.before_date_edit = QDateEdit(QDate.currentDate())
        self.before_date_edit.setCalendarPopup(True)
        date_row.addWidget(self.before_date_edit)
        layout.addLayout(date_row)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(_CONFLICT_OPTIONS)
        conflict_row.addWidget(self.conflict_combo)
        self.no_verify_checkbox = QCheckBox("Skip verification")
        conflict_row.addWidget(self.no_verify_checkbox)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        btn_row = QHBoxLayout()
        self.restore_button = QPushButton("Restore")
        btn_row.addWidget(self.restore_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.results_table = QTableWidget(0, len(_RESULT_COLUMNS))
        self.results_table.setHorizontalHeaderLabels(_RESULT_COLUMNS)
        layout.addWidget(self.results_table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.restore_button.clicked.connect(self._on_restore)
        self.viewmodel.busyChanged.connect(lambda busy: self.restore_button.setEnabled(not busy))
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._on_results)

    def refresh_sources(self):
        self.sources_list.clear()
        for source in self.viewmodel.list_sources(self._get_profile()):
            item = QListWidgetItem(source)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.sources_list.addItem(item)

    def _selected_sources(self):
        return [
            self.sources_list.item(i).text()
            for i in range(self.sources_list.count())
            if self.sources_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _on_restore(self):
        after = self.after_date_edit.date().toPyDate() if self.date_filter_checkbox.isChecked() else None
        before = self.before_date_edit.date().toPyDate() if self.date_filter_checkbox.isChecked() else None
        conflict_text = self.conflict_combo.currentText()
        conflict = None if conflict_text == "(profile default)" else conflict_text
        self.viewmodel.run_restore(
            self._get_profile(), self._selected_sources(), after, before, conflict, self.no_verify_checkbox.isChecked()
        )

    def _on_results(self, results):
        self.results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            values = [result["source"], str(result["done"]), str(result["total"]), str(result["failed"]), str(result["verified"])]
            for col, value in enumerate(values):
                self.results_table.setItem(row, col, QTableWidgetItem(value))
