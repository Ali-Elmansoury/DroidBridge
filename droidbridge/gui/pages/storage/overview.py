from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.storage.overview import OverviewViewModel

_COLS = ["Category", "Size"]


class OverviewPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = OverviewViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Refresh the device storage usage breakdown.")
        row.addWidget(self.refresh_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.total_label = QLabel("-")
        self.used_label = QLabel("-")
        self.free_label = QLabel("-")
        form = QFormLayout()
        form.addRow("Total:", self.total_label)
        form.addRow("Used:", self.used_label)
        form.addRow("Free:", self.free_label)
        layout.addLayout(form)

        self.usage_bar = QProgressBar()
        self.usage_bar.setRange(0, 100)
        layout.addWidget(self.usage_bar)

        self.categories_table = QTableWidget(0, len(_COLS))
        self.categories_table.setHorizontalHeaderLabels(_COLS)
        self.categories_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.categories_table)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect(self):
        self.refresh_button.clicked.connect(self._on_refresh)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultChanged.connect(self._populate)

    def _on_refresh(self):
        self.viewmodel.refresh()

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.refresh_button.setEnabled(not busy)

    def _populate(self, result):
        self.total_label.setText(result["total_str"])
        self.used_label.setText(result["used_str"])
        self.free_label.setText(result["free_str"])
        self.usage_bar.setValue(result["percent"])
        categories = result["categories"]
        self.categories_table.setRowCount(len(categories))
        for r, cat in enumerate(categories):
            self.categories_table.setItem(r, 0, QTableWidgetItem(cat["label"]))
            self.categories_table.setItem(r, 1, QTableWidgetItem(cat["size_str"]))
