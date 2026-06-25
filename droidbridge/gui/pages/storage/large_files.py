from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.storage.large_files import LargeFilesViewModel
from droidbridge.modules import search as search_module
from droidbridge.utils.format import parse_size

_COLS = ["Size", "Path", "Modified"]


class LargeFilesPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = LargeFilesViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Root:"))
        self.root_edit = QLineEdit(search_module.DEFAULT_ROOT)
        self.root_edit.setToolTip("Device path to scan for large files.")
        row.addWidget(self.root_edit)
        row.addWidget(QLabel("Min size:"))
        self.min_size_edit = QLineEdit()
        self.min_size_edit.setPlaceholderText("e.g. 50MB")
        self.min_size_edit.setToolTip("Minimum file size to include, e.g. 50MB. Leave blank for no minimum.")
        row.addWidget(self.min_size_edit)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setToolTip("Scan the device for files at or above the minimum size.")
        row.addWidget(self.scan_button)
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.results_table = QTableWidget(0, len(_COLS))
        self.results_table.setHorizontalHeaderLabels(_COLS)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)

        self.empty_label = QLabel("No large files found.")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def _connect(self):
        self.scan_button.clicked.connect(self._on_scan)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _on_scan(self):
        root = self.root_edit.text().strip() or search_module.DEFAULT_ROOT
        text = self.min_size_edit.text().strip()
        threshold = None
        if text:
            try:
                threshold = parse_size(text)
            except ValueError:
                self.viewmodel.logMessage.emit(f"Invalid min size: {text!r}", "WARNING")
                return
        self.viewmodel.scan(root, threshold=threshold)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.scan_button.setEnabled(not busy)

    def _populate(self, results):
        self.results_table.setRowCount(len(results))
        for r, item in enumerate(results):
            self.results_table.setItem(r, 0, QTableWidgetItem(item["size_str"]))
            self.results_table.setItem(r, 1, QTableWidgetItem(item["path"]))
            self.results_table.setItem(r, 2, QTableWidgetItem(item["modified_str"]))
        self.empty_label.setVisible(len(results) == 0)
        self.results_table.setVisible(len(results) > 0)
