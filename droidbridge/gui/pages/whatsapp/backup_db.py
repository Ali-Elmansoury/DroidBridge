# Copyright (c) 2026 Ali Elmansoury. All rights reserved.
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QVBoxLayout, QWidget, QLineEdit,
)
from droidbridge.gui.viewmodels.whatsapp.backup_db import BackupDbViewModel
from droidbridge.modules.whatsapp import MSGSTORE_WARNING

_CONFLICT_OPTIONS = ["skip", "overwrite", "rename"]
_SCOPE_NOTE = (
    "Backs up the Databases/, Backups/, and accounts/ folders. Backups/ can "
    "include sticker-pack files and other large caches, so the file count "
    "may be far higher than just the chat databases.\n\n" + MSGSTORE_WARNING
)


class BackupDbPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = BackupDbViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.scope_label = QLabel(_SCOPE_NOTE)
        self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setToolTip("Local directory where WhatsApp database files will be backed up.")
        dest_row.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.setToolTip("How to handle database files that already exist at the destination.")
        self.conflict_combo.addItems(_CONFLICT_OPTIONS)
        conflict_row.addWidget(self.conflict_combo)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        self.verify_checkbox = QCheckBox("Verify after backup")
        self.verify_checkbox.setChecked(True)
        self.verify_checkbox.setToolTip("Confirm every pulled database file matches the device original by size.")
        layout.addWidget(self.verify_checkbox)

        btn_row = QHBoxLayout()
        self.backup_db_button = QPushButton("Backup Databases")
        btn_row.addWidget(self.backup_db_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)
        layout.addWidget(self.progress_label)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def _connect(self):
        self.backup_db_button.clicked.connect(self._on_backup_db)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.progressChanged.connect(self._on_progress)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select backup destination")
        if path:
            self.dest_edit.setText(path)

    def _on_backup_db(self):
        self.viewmodel.backup_db(
            self._get_app(), self.dest_edit.text(),
            self.conflict_combo.currentText(), self.verify_checkbox.isChecked(),
        )

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.backup_db_button.setEnabled(not busy)

    def _on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"{done} / {total} files")
