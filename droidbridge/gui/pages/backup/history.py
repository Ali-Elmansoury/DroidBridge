# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from droidbridge.gui.viewmodels.backup.history import HistoryViewModel

_COLUMNS = ["Profile", "Timestamp", "Files", "Bytes", "Duration (s)", "Destination", "Verified"]


class HistoryPanel(QWidget):
    def __init__(self, get_profile, parent=None):
        super().__init__(parent)
        self._get_profile = get_profile
        self.viewmodel = HistoryViewModel()
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        btn_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Reload the backup history for the selected profile.")
        btn_row.addWidget(self.refresh_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        layout.addWidget(self.table)

        self.outdated_label = QLabel()
        self.outdated_label.setWordWrap(True)
        layout.addWidget(self.outdated_label)

        self.comparison_label = QLabel()
        self.comparison_label.setWordWrap(True)
        layout.addWidget(self.comparison_label)

    def _connect(self):
        self.refresh_button.clicked.connect(self._on_refresh)
        self.viewmodel.historyChanged.connect(self._on_history)

    def _on_refresh(self):
        self.viewmodel.refresh(self._get_profile())

    def _on_history(self, result):
        records = result["records"]
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            values = [
                record.profile, record.timestamp, str(record.file_count), str(record.total_bytes),
                str(record.duration_seconds), record.destination, str(record.verified),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

        if result["outdated"] is None:
            self.outdated_label.setText("")
        elif result["outdated"]:
            self.outdated_label.setText("This profile's last backup is outdated.")
        else:
            self.outdated_label.setText("This profile's last backup is up to date.")

        comparison = result["comparison"]
        if comparison is None:
            self.comparison_label.setText("")
        else:
            self.comparison_label.setText(
                f"Since previous backup: {comparison['file_count_delta']:+d} files, "
                f"{comparison['total_bytes_delta']:+d} bytes."
            )
