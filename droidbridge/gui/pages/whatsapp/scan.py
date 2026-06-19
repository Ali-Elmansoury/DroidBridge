from PyQt6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.whatsapp.scan import ScanViewModel

_BREAKDOWN_KEYS = ["folder", "year", "extension"]
_COLUMNS = {
    "folder": ["Folder Type", "Section", "Files", "Size"],
    "year": ["Year-Month", "Files", "Size"],
    "extension": ["Extension", "Files", "Size"],
}
_ROW_KEYS = {
    "folder": ["folder_type", "section", "file_count", "total_size_str"],
    "year": ["year_month", "file_count", "total_size_str"],
    "extension": ["extension", "file_count", "total_size_str"],
}


class ScanPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = ScanViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Breakdown:"))
        self.breakdown_combo = QComboBox()
        self.breakdown_combo.setToolTip("Group results by folder type, year/month, or file extension.")
        self.breakdown_combo.addItems(["Folder", "Year", "Extension"])
        row.addWidget(self.breakdown_combo)
        self.scan_button = QPushButton("Scan")
        row.addWidget(self.scan_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(_COLUMNS["folder"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.results_table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.scan_button.clicked.connect(self._on_scan)
        self.breakdown_combo.currentIndexChanged.connect(self._update_columns)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _update_columns(self):
        key = _BREAKDOWN_KEYS[self.breakdown_combo.currentIndex()]
        cols = _COLUMNS[key]
        self.results_table.setColumnCount(len(cols))
        self.results_table.setHorizontalHeaderLabels(cols)
        self.results_table.setRowCount(0)

    def _on_scan(self):
        key = _BREAKDOWN_KEYS[self.breakdown_combo.currentIndex()]
        self.viewmodel.scan(self._get_app(), key)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.scan_button.setEnabled(not busy)

    def _populate(self, rows):
        key = _BREAKDOWN_KEYS[self.breakdown_combo.currentIndex()]
        keys = _ROW_KEYS[key]
        cols = _COLUMNS[key]
        self.results_table.setColumnCount(len(cols))
        self.results_table.setHorizontalHeaderLabels(cols)
        self.results_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, k in enumerate(keys):
                self.results_table.setItem(r, c, QTableWidgetItem(str(row.get(k, ""))))
