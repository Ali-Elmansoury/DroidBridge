import datetime
from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QAbstractItemView, QDateEdit, QFileDialog, QHBoxLayout, QInputDialog,
    QLabel, QListWidget, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget, QLineEdit,
)
from droidbridge.gui.viewmodels.whatsapp.delete import DeleteViewModel
from droidbridge.modules.whatsapp import BACKUP_TYPES
from droidbridge.gui.widgets.export_button import export_report
from droidbridge.reports.generators import Report, ReportSection

_PREVIEW_COLS = ["Path", "Folder Type", "Size"]
_PREVIEW_KEYS = ["path", "folder_type", "size_str"]


class DeletePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = DeleteViewModel(context)
        self._rows = []
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Delete files before:"))
        self.before_date = QDateEdit(QDate(2024, 1, 1))
        self.before_date.setCalendarPopup(True)
        self.before_date.setToolTip("Files with a date older than this will be candidates for deletion.")
        date_row.addWidget(self.before_date)
        date_row.addStretch()
        layout.addLayout(date_row)

        layout.addWidget(QLabel("Keep types (nothing = delete all matching):"))
        self.keep_list = QListWidget()
        self.keep_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.keep_list.setToolTip("Select types to keep even if they match the date filter.")
        for label in BACKUP_TYPES.values():
            self.keep_list.addItem(label)
        self.keep_list.setFixedHeight(100)
        layout.addWidget(self.keep_list)

        backup_row = QHBoxLayout()
        backup_row.addWidget(QLabel("Verified backup dir:"))
        self.backup_dir_edit = QLineEdit()
        self.backup_dir_edit.setToolTip(
            "Optional: path to a backup directory. "
            "Preview will abort if any file to be deleted is missing from this backup."
        )
        backup_row.addWidget(self.backup_dir_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_backup)
        backup_row.addWidget(browse_btn)
        layout.addLayout(backup_row)

        btn_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview")
        btn_row.addWidget(self.preview_button)
        self.delete_button = QPushButton("Delete…")
        self.delete_button.setEnabled(False)
        self.delete_button.setToolTip("Run preview first. Will ask for 'YES DELETE' confirmation.")
        btn_row.addWidget(self.delete_button)
        self.export_button = QPushButton("Export...")
        self.export_button.setToolTip(
            "Export the delete preview to TXT, CSV, HTML, or JSON — "
            "save a record before confirming deletion."
        )
        self.export_button.setEnabled(False)
        btn_row.addWidget(self.export_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.preview_table = QTableWidget(0, len(_PREVIEW_COLS))
        self.preview_table.setHorizontalHeaderLabels(_PREVIEW_COLS)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_table.setVisible(False)
        layout.addWidget(self.preview_table)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.preview_button.clicked.connect(self._on_preview)
        self.delete_button.clicked.connect(self._on_delete)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.resultsChanged.connect(self._populate)

    def _browse_backup(self):
        path = QFileDialog.getExistingDirectory(self, "Select verified backup directory")
        if path:
            self.backup_dir_edit.setText(path)

    def _on_preview(self):
        qdate = self.before_date.date()
        before = datetime.date(qdate.year(), qdate.month(), qdate.day())
        selected = [self.keep_list.item(i).text()
                    for i in range(self.keep_list.count())
                    if self.keep_list.item(i).isSelected()]
        keep_types = selected if selected else None
        self.viewmodel.preview(self._get_app(), before, keep_types, self.backup_dir_edit.text())

    def _on_delete(self):
        text, ok = QInputDialog.getText(self, "Confirm Deletion",
                                        "This will permanently delete files from the device.\n"
                                        "Type 'YES DELETE' to confirm:")
        if not ok or text != "YES DELETE":
            return
        self.viewmodel.execute()

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.preview_button.setEnabled(not busy)

    def _on_export_clicked(self):
        if not self._rows:
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        section = ReportSection(
            title="Delete Preview",
            headers=_PREVIEW_COLS,
            rows=[[str(row.get(k, "")) for k in _PREVIEW_KEYS] for row in self._rows],
        )
        export_report(
            self, "Export Delete Preview", f"delete_preview_{ts}.txt",
            Report(title="Delete Preview", sections=[section]),
        )

    def _populate(self, rows):
        self._rows = rows
        has_rows = bool(rows)
        self.delete_button.setEnabled(has_rows)
        self.export_button.setEnabled(has_rows)
        self.preview_table.setVisible(has_rows)
        self.preview_table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, key in enumerate(_PREVIEW_KEYS):
                self.preview_table.setItem(r, c, QTableWidgetItem(str(row.get(key, ""))))
