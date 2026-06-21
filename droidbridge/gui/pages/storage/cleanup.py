from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.storage.cleanup import CleanupViewModel

_COLS = ["Title", "Description", "Estimated Recoverable", "Item Count"]


class CleanupPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = CleanupViewModel(context)
        self._suggestions = []
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        row.addWidget(self.refresh_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.suggestions_table = QTableWidget(0, len(_COLS))
        self.suggestions_table.setHorizontalHeaderLabels(_COLS)
        self.suggestions_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.suggestions_table)

        self.empty_label = QLabel("No cleanup suggestions found.")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        layout.addWidget(QLabel("Items:"))
        self.items_list = QListWidget()
        layout.addWidget(self.items_list)

        self.items_overflow_label = QLabel()
        self.items_overflow_label.setVisible(False)
        layout.addWidget(self.items_overflow_label)

        self.total_label = QLabel()
        layout.addWidget(self.total_label)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.refresh_button.clicked.connect(self._on_refresh)
        self.suggestions_table.itemSelectionChanged.connect(self._on_suggestion_selected)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultChanged.connect(self._populate)

    def _on_refresh(self):
        self.viewmodel.refresh()

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.refresh_button.setEnabled(not busy)

    def _populate(self, result):
        self._suggestions = result["suggestions"]
        self.suggestions_table.setRowCount(len(self._suggestions))
        for r, item in enumerate(self._suggestions):
            self.suggestions_table.setItem(r, 0, QTableWidgetItem(item["title"]))
            self.suggestions_table.setItem(r, 1, QTableWidgetItem(item["description"]))
            self.suggestions_table.setItem(r, 2, QTableWidgetItem(item["estimated_bytes_str"]))
            self.suggestions_table.setItem(r, 3, QTableWidgetItem(str(item["item_count"])))
        self.items_list.clear()
        self.items_overflow_label.setVisible(False)
        self.empty_label.setVisible(len(self._suggestions) == 0)
        self.suggestions_table.setVisible(len(self._suggestions) > 0)
        self.total_label.setText(f"Total estimated recoverable: {result['total_str']}")

    def _on_suggestion_selected(self):
        rows = self.suggestions_table.selectionModel().selectedRows()
        self.items_list.clear()
        if not rows:
            self.items_overflow_label.setVisible(False)
            return
        suggestion = self._suggestions[rows[0].row()]
        self.items_list.addItems(suggestion["items"])
        overflow = suggestion["item_overflow"]
        self.items_overflow_label.setVisible(overflow > 0)
        if overflow > 0:
            self.items_overflow_label.setText(f"... and {overflow} more item(s)")
