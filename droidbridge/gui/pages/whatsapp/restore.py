from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QVBoxLayout, QWidget, QLineEdit,
)
from droidbridge.gui.viewmodels.whatsapp.restore import RestoreViewModel

_CONFLICT_OPTIONS = ["skip", "overwrite", "rename"]


class RestorePanel(QWidget):
    def __init__(self, context, get_app, parent=None):
        super().__init__(parent)
        self._get_app = get_app
        self.viewmodel = RestoreViewModel(context)
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        src_row = QHBoxLayout()
        src_row.addWidget(QLabel("Source:"))
        self.src_edit = QLineEdit()
        self.src_edit.setToolTip("Local backup directory created by a previous Backup operation.")
        src_row.addWidget(self.src_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_src)
        src_row.addWidget(browse_btn)
        layout.addLayout(src_row)

        conflict_row = QHBoxLayout()
        conflict_row.addWidget(QLabel("Conflict:"))
        self.conflict_combo = QComboBox()
        self.conflict_combo.setToolTip("How to handle files that already exist on the device.")
        self.conflict_combo.addItems(_CONFLICT_OPTIONS)
        conflict_row.addWidget(self.conflict_combo)
        conflict_row.addStretch()
        layout.addLayout(conflict_row)

        self.verify_checkbox = QCheckBox("Verify after restore")
        self.verify_checkbox.setChecked(True)
        self.verify_checkbox.setToolTip("Confirm every pushed file matches the source by size.")
        layout.addWidget(self.verify_checkbox)

        btn_row = QHBoxLayout()
        self.restore_button = QPushButton("Restore")
        btn_row.addWidget(self.restore_button)
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

    def _connect(self):
        self.restore_button.clicked.connect(self._on_restore)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self.status_label.setText)
        self.viewmodel.progressChanged.connect(self._on_progress)

    def _browse_src(self):
        path = QFileDialog.getExistingDirectory(self, "Select backup source directory")
        if path:
            self.src_edit.setText(path)

    def _on_restore(self):
        self.viewmodel.restore(
            self._get_app(), self.src_edit.text(),
            self.conflict_combo.currentText(), self.verify_checkbox.isChecked(),
        )

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
        self.restore_button.setEnabled(not busy)

    def _on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)
        self.progress_label.setText(f"{done} / {total} files")
