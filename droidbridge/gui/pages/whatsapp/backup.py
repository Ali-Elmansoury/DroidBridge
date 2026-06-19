from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QProgressBar, QPushButton, QVBoxLayout, QWidget, QLineEdit,
    QAbstractItemView,
)
from droidbridge.gui.viewmodels.whatsapp.backup import BackupViewModel
from droidbridge.modules.whatsapp import BACKUP_TYPES

_CONFLICT_OPTIONS = ["skip", "overwrite", "rename"]


class BackupPanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = BackupViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("Destination:"))
        self.dest_edit = QLineEdit()
        self.dest_edit.setToolTip("Local directory where WhatsApp media will be backed up.")
        dest_row.addWidget(self.dest_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        layout.addWidget(QLabel("Types (nothing selected = full backup):"))
        self.type_list = QListWidget()
        self.type_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.type_list.setToolTip("Select specific media types to back up, or leave empty for a full backup.")
        for key in BACKUP_TYPES:
            self.type_list.addItem(key)
        self.type_list.setFixedHeight(120)
        layout.addWidget(self.type_list)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.setToolTip("How to handle files that already exist at the destination.")
        self.conflict_combo.addItems(_CONFLICT_OPTIONS)
        conflict_row.addWidget(self.conflict_combo)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        self.verify_checkbox = QCheckBox("Verify after backup")
        self.verify_checkbox.setChecked(True)
        self.verify_checkbox.setToolTip("Confirm every pulled file matches the device original by size.")
        layout.addWidget(self.verify_checkbox)

        btn_row = QHBoxLayout()
        self.backup_button = QPushButton("Backup")
        btn_row.addWidget(self.backup_button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        layout.addWidget(self.progress_label)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

    def _connect(self):
        self.backup_button.clicked.connect(self._on_backup)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.progressChanged.connect(self._on_progress)

    def _browse_dest(self):
        path = QFileDialog.getExistingDirectory(self, "Select backup destination")
        if path:
            self.dest_edit.setText(path)

    def _on_backup(self):
        selected = [self.type_list.item(i).text()
                    for i in range(self.type_list.count())
                    if self.type_list.item(i).isSelected()]
        types = selected if selected else None
        self.viewmodel.backup(
            self._get_app(), self.dest_edit.text(), types,
            self.conflict_combo.currentText(), self.verify_checkbox.isChecked(),
        )

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.backup_button.setEnabled(not busy)

    def _on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"{done} / {total} files")
