# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
import datetime
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.whatsapp.analyze import AnalyzeViewModel

_COLS = ["Folder Type", "Pre Files", "Pre Size", "Post Files", "Post Size", "Unknown Files", "Unknown Size"]
_KEYS = ["folder_type", "pre_count", "pre_size_str", "post_count", "post_size_str", "unknown_count", "unknown_size_str"]


class AnalyzePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = AnalyzeViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Cutoff date:"))
        self.cutoff_date = QDateEdit(QDate(2024, 9, 1))
        self.cutoff_date.setCalendarPopup(True)
        self.cutoff_date.setToolTip("Files before this date are considered 'pre-cutoff'.")
        row.addWidget(self.cutoff_date)
        self.analyze_button = QPushButton("Analyze")
        row.addWidget(self.analyze_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.results_table = QTableWidget(0, len(_COLS))
        self.results_table.setHorizontalHeaderLabels(_COLS)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect(self):
        self.analyze_button.clicked.connect(self._on_analyze)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _on_analyze(self):
        qdate = self.cutoff_date.date()
        cutoff = datetime.date(qdate.year(), qdate.month(), qdate.day())
        self.viewmodel.analyze(self._get_app(), cutoff)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.analyze_button.setEnabled(not busy)

    def _populate(self, rows):
        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(_KEYS):
                self.results_table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))
