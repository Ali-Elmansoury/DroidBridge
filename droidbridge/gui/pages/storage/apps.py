from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.storage.apps import AppsViewModel

_COLS = ["Package", "Total", "APK", "Data", "Cache", "Kind"]
_KEYS = ["package", "total_size_str", "apk_size_str", "data_size_str", "cache_size_str", "kind"]
_FILTER_LABELS = ["All apps", "System apps only", "User apps only"]
_FILTER_VALUES = [None, "system", "user"]


class AppsPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = AppsViewModel(context)
        self._all_rows = []
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Top:"))
        self.top_spin = QSpinBox()
        self.top_spin.setRange(1, 9999)
        self.top_spin.setValue(20)
        row.addWidget(self.top_spin)
        self.show_all_checkbox = QCheckBox("Show all")
        row.addWidget(self.show_all_checkbox)
        row.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(_FILTER_LABELS)
        row.addWidget(self.filter_combo)
        self.refresh_button = QPushButton("Refresh")
        row.addWidget(self.refresh_button)
        row.addStretch()
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.apps_table = QTableWidget(0, len(_COLS))
        self.apps_table.setHorizontalHeaderLabels(_COLS)
        self.apps_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.apps_table)

        self.empty_label = QLabel("No apps found.")
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.show_all_checkbox.toggled.connect(lambda checked: self.top_spin.setEnabled(not checked))
        self.refresh_button.clicked.connect(self._on_refresh)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _on_refresh(self):
        filter_kind = _FILTER_VALUES[self.filter_combo.currentIndex()]
        self.viewmodel.load(filter_kind=filter_kind)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.refresh_button.setEnabled(not busy)

    def _populate(self, rows):
        self._all_rows = rows
        visible_rows = rows if self.show_all_checkbox.isChecked() else rows[: self.top_spin.value()]
        is_empty = not visible_rows
        self.empty_label.setVisible(is_empty)
        self.apps_table.setVisible(not is_empty)
        self.apps_table.setRowCount(len(visible_rows))
        for r, row in enumerate(visible_rows):
            for c, key in enumerate(_KEYS):
                self.apps_table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))
