from datetime import datetime
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from droidbridge.gui.viewmodels.apps.listing import ListingViewModel
from droidbridge.gui.widgets.export_button import export_report
from droidbridge.reports.generators import Report, ReportSection

_COLS = ["Package", "Version", "Installed", "Updated", "APK", "Data", "Cache", "Total", "Kind", "Status"]
_KEYS = [
    "package", "version_name", "installed_str", "updated_str",
    "apk_size_str", "data_size_str", "cache_size_str", "total_size_str", "kind", "status",
]
_FILTER_LABELS = ["All", "System", "User"]
_FILTER_VALUES = ["all", "system", "user"]
_SORT_LABELS = ["Name", "Total", "APK", "Data", "Cache", "Install Date", "Update Date"]
_SORT_VALUES = ["name", "total", "apk", "data", "cache", "install_date", "update_date"]


class ListingPanel(QWidget):
    appSelected = pyqtSignal(str)

    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = ListingViewModel(context)
        self._rows = []
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Filter:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(_FILTER_LABELS)
        self.filter_combo.setToolTip("Limit the list to system apps, user apps, or all apps.")
        row.addWidget(self.filter_combo)
        row.addWidget(QLabel("Sort:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(_SORT_LABELS)
        self.sort_combo.setToolTip("Sort the app list by this field.")
        row.addWidget(self.sort_combo)
        self.descending_checkbox = QCheckBox("Descending")
        self.descending_checkbox.setToolTip("Sort the app list in descending order.")
        row.addWidget(self.descending_checkbox)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setToolTip("Refresh the installed app list with the current filter and sort.")
        row.addWidget(self.refresh_button)
        row.addStretch()
        self.export_button = QPushButton("Export...")
        self.export_button.setToolTip("Export the current app list to TXT, CSV, HTML, or JSON.")
        self.export_button.setEnabled(False)
        row.addWidget(self.export_button)
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.apps_table = QTableWidget(0, len(_COLS))
        self.apps_table.setHorizontalHeaderLabels(_COLS)
        self.apps_table.horizontalHeader().setStretchLastSection(True)
        self.apps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.apps_table.resizeColumnsToContents()
        self.apps_table.setToolTip("Select an app to act on it in the other Apps tabs.")
        layout.addWidget(self.apps_table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.refresh_button.clicked.connect(self._on_refresh)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.apps_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _on_refresh(self):
        filter_kind = _FILTER_VALUES[self.filter_combo.currentIndex()]
        sort_by = _SORT_VALUES[self.sort_combo.currentIndex()]
        reverse = self.descending_checkbox.isChecked()
        self.viewmodel.load(filter_kind=filter_kind, sort_by=sort_by, reverse=reverse)

    def refresh(self):
        """Reload using the currently selected filter/sort/order. Public entry
        point for Task 10's coordinator to trigger after an Uninstall succeeds."""
        self._on_refresh()

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.refresh_button.setEnabled(not busy)

    def _populate(self, rows):
        self._rows = rows
        self.export_button.setEnabled(bool(rows))
        self.apps_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(_KEYS):
                self.apps_table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))

    def _on_selection_changed(self):
        selected_rows = {item.row() for item in self.apps_table.selectedItems()}
        if not selected_rows:
            self.appSelected.emit("")
            return
        row_index = next(iter(selected_rows))
        self.appSelected.emit(self._rows[row_index]["package"])

    def clear_selection(self):
        self.apps_table.clearSelection()
        self.appSelected.emit("")

    def update_row_status(self, package, is_disabled):
        status = "Disabled" if is_disabled else "Enabled"
        for r, row in enumerate(self._rows):
            if row["package"] == package:
                row["is_disabled"] = is_disabled
                row["status"] = status
                self.apps_table.setItem(r, _KEYS.index("status"), QTableWidgetItem(status))
                return

    def _on_export_clicked(self):
        if not self._rows:
            return
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        section = ReportSection(
            title="App List",
            headers=_COLS,
            rows=[[str(row.get(k, "")) for k in _KEYS] for row in self._rows],
        )
        export_report(
            self, "Export App List", f"app_list_{ts}.txt",
            Report(title="App List", sections=[section]),
        )
