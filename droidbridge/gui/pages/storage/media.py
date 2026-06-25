import datetime
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDateEdit, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QProgressBar, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from droidbridge.gui.viewmodels.storage.media import MediaViewModel
from droidbridge.gui.widgets.export_button import export_report
from droidbridge.reports.generators import Report, ReportSection
from droidbridge.modules import search as search_module

_CATEGORY_COLS = ["Type", "Count", "Size"]
_LARGEST_COLS = ["Size", "Path"]
_DUPLICATE_COLS = ["Name", "Size", "Count"]


class MediaPanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = MediaViewModel(context)
        self._duplicate_groups = []
        self._last_result = None
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Root:"))
        self.root_edit = QLineEdit(search_module.DEFAULT_ROOT)
        self.root_edit.setToolTip("Device path to scan for media files.")
        row.addWidget(self.root_edit)
        self.before_checkbox = QCheckBox("Filter by date (before):")
        self.before_checkbox.setToolTip("Include only media files modified before the date on the right.")
        row.addWidget(self.before_checkbox)
        self.before_date_edit = QDateEdit(QDate.currentDate())
        self.before_date_edit.setCalendarPopup(True)
        self.before_date_edit.setEnabled(False)
        self.before_date_edit.setToolTip("Latest modification date to include in the scan.")
        row.addWidget(self.before_date_edit)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setToolTip("Scan the device for media files, categorize them, and find duplicates.")
        row.addWidget(self.scan_button)
        self.export_button = QPushButton("Export...")
        self.export_button.setToolTip("Export the media scan results to TXT, CSV, HTML, or JSON.")
        self.export_button.setEnabled(False)
        row.addWidget(self.export_button)
        layout.addLayout(row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)

        self.categories_table = QTableWidget(0, len(_CATEGORY_COLS))
        self.categories_table.setHorizontalHeaderLabels(_CATEGORY_COLS)
        self.categories_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.categories_table)

        layout.addWidget(QLabel("Largest files:"))
        self.largest_files_table = QTableWidget(0, len(_LARGEST_COLS))
        self.largest_files_table.setHorizontalHeaderLabels(_LARGEST_COLS)
        self.largest_files_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.largest_files_table)

        layout.addWidget(QLabel("Duplicate groups:"))
        self.duplicates_table = QTableWidget(0, len(_DUPLICATE_COLS))
        self.duplicates_table.setHorizontalHeaderLabels(_DUPLICATE_COLS)
        self.duplicates_table.horizontalHeader().setStretchLastSection(True)
        self.duplicates_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.duplicates_table.setToolTip("Select a duplicate group to view its file paths below.")
        layout.addWidget(self.duplicates_table)

        self.duplicates_overflow_label = QLabel()
        self.duplicates_overflow_label.setVisible(False)
        layout.addWidget(self.duplicates_overflow_label)

        layout.addWidget(QLabel("Paths in selected group:"))
        self.duplicates_paths_list = QListWidget()
        self.duplicates_paths_list.setToolTip("Full device paths of files in the duplicate group selected above.")
        layout.addWidget(self.duplicates_paths_list)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.before_checkbox.toggled.connect(self.before_date_edit.setEnabled)
        self.scan_button.clicked.connect(self._on_scan)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.duplicates_table.itemSelectionChanged.connect(self._on_group_selected)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultChanged.connect(self._populate)

    def _on_scan(self):
        root = self.root_edit.text().strip() or search_module.DEFAULT_ROOT
        before = None
        if self.before_checkbox.isChecked():
            qdate = self.before_date_edit.date()
            before = datetime.datetime(qdate.year(), qdate.month(), qdate.day())
        self.viewmodel.scan(root, before=before)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.scan_button.setEnabled(not busy)

    def _populate(self, result):
        self._last_result = result
        self.export_button.setEnabled(True)
        self.summary_label.setText(f"{result['total_count']} file(s), {result['total_size_str']}")

        categories = result["categories"]
        self.categories_table.setRowCount(len(categories))
        for r, cat in enumerate(categories):
            self.categories_table.setItem(r, 0, QTableWidgetItem(cat["type"]))
            self.categories_table.setItem(r, 1, QTableWidgetItem(str(cat["count"])))
            self.categories_table.setItem(r, 2, QTableWidgetItem(cat["size_str"]))

        largest = result["largest_files"]
        self.largest_files_table.setRowCount(len(largest))
        for r, item in enumerate(largest):
            self.largest_files_table.setItem(r, 0, QTableWidgetItem(item["size_str"]))
            self.largest_files_table.setItem(r, 1, QTableWidgetItem(item["path"]))

        self._duplicate_groups = result["duplicate_groups"]
        self.duplicates_table.setRowCount(len(self._duplicate_groups))
        for r, group in enumerate(self._duplicate_groups):
            self.duplicates_table.setItem(r, 0, QTableWidgetItem(group["name"]))
            self.duplicates_table.setItem(r, 1, QTableWidgetItem(group["size_str"]))
            self.duplicates_table.setItem(r, 2, QTableWidgetItem(str(group["count"])))
        self.duplicates_paths_list.clear()

        overflow = result["duplicate_overflow"]
        self.duplicates_overflow_label.setVisible(overflow > 0)
        if overflow > 0:
            self.duplicates_overflow_label.setText(f"... and {overflow} more group(s)")

    def _on_group_selected(self):
        rows = self.duplicates_table.selectionModel().selectedRows()
        self.duplicates_paths_list.clear()
        if not rows:
            return
        group = self._duplicate_groups[rows[0].row()]
        self.duplicates_paths_list.addItems(group["paths"])

    def _on_export_clicked(self):
        if self._last_result is None:
            return
        result = self._last_result
        cat_section = ReportSection(
            title="Categories",
            headers=_CATEGORY_COLS,
            rows=[[cat["type"], str(cat["count"]), cat["size_str"]] for cat in result["categories"]],
        )
        largest_section = ReportSection(
            title="Largest Files",
            headers=_LARGEST_COLS,
            rows=[[item["size_str"], item["path"]] for item in result["largest_files"]],
        )
        dups_section = ReportSection(
            title="Duplicate Groups",
            headers=_DUPLICATE_COLS,
            rows=[[g["name"], g["size_str"], str(g["count"])] for g in result["duplicate_groups"]],
        )
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        export_report(
            self, "Export Media Scan", f"media_scan_{ts}.txt",
            Report(title="Media Scan", sections=[cat_section, largest_section, dups_section]),
        )
