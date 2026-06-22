from PyQt6.QtWidgets import (
    QCheckBox, QFileDialog, QGroupBox, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from droidbridge.gui.viewmodels.apps.backup_restore import BackupRestoreViewModel

_NO_SELECTION_TEXT = "No app selected — select one in the Listing tab."
_NO_BUNDLE_TEXT = "No backup folder selected."


class BackupRestorePanel(QWidget):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.viewmodel = BackupRestoreViewModel(context)
        self._current_app = None
        self._current_bundle_dir = None
        self._current_manifest = None
        self._build_ui()
        self._connect()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        backup_box = QGroupBox("Backup")
        backup_layout = QVBoxLayout(backup_box)
        self.acting_on_label = QLabel(_NO_SELECTION_TEXT)
        backup_layout.addWidget(self.acting_on_label)
        self.backup_button = QPushButton("Backup APK...")
        self.backup_button.setEnabled(False)
        backup_layout.addWidget(self.backup_button)
        self.backup_status_label = QLabel()
        backup_layout.addWidget(self.backup_status_label)
        layout.addWidget(backup_box)

        restore_box = QGroupBox("Restore")
        restore_layout = QVBoxLayout(restore_box)
        self.browse_button = QPushButton("Browse...")
        restore_layout.addWidget(self.browse_button)
        self.manifest_label = QLabel(_NO_BUNDLE_TEXT)
        restore_layout.addWidget(self.manifest_label)
        self.allow_downgrade_checkbox = QCheckBox("Allow downgrade")
        restore_layout.addWidget(self.allow_downgrade_checkbox)
        self.restore_button = QPushButton("Restore")
        self.restore_button.setEnabled(False)
        restore_layout.addWidget(self.restore_button)
        self.restore_status_label = QLabel()
        restore_layout.addWidget(self.restore_status_label)
        layout.addWidget(restore_box)

        layout.addStretch()

    def _connect(self):
        self.backup_button.clicked.connect(self._on_backup)
        self.browse_button.clicked.connect(self._on_browse)
        self.restore_button.clicked.connect(self._on_restore)
        self.viewmodel.busyChanged.connect(self._on_busy)
        self.viewmodel.statusChanged.connect(self._on_status)
        self.viewmodel.appInfoChanged.connect(self._on_app_info)
        self.viewmodel.backupFinished.connect(self._on_backup_finished)
        self.viewmodel.manifestChanged.connect(self._on_manifest)
        self.viewmodel.restoreFinished.connect(self._on_restore_finished)

    def set_current_app(self, package):
        self.viewmodel.set_current_app(package or None)

    def _on_app_info(self, app):
        self._current_app = app
        if app is None:
            self.acting_on_label.setText(_NO_SELECTION_TEXT)
            self.backup_button.setEnabled(False)
            return
        self.acting_on_label.setText(f"Acting on: {app['package']} (v{app['version_name']})")
        self.backup_button.setEnabled(True)

    def _on_backup(self):
        if self._current_app is None:
            return
        dest_dir = QFileDialog.getExistingDirectory(self, "Select backup folder")
        if not dest_dir:
            return
        self.viewmodel.backup(
            self._current_app["package"], self._current_app["version_name"],
            self._current_app["version_code"], dest_dir,
        )

    def _on_backup_finished(self, bundle_dir):
        self.backup_status_label.setText(f"Backed up to {bundle_dir}")

    def _on_browse(self):
        bundle_dir = QFileDialog.getExistingDirectory(self, "Select backup bundle folder")
        if not bundle_dir:
            return
        self._current_bundle_dir = bundle_dir
        self.viewmodel.load_manifest(bundle_dir)

    def _on_manifest(self, manifest):
        self._current_manifest = manifest
        if manifest is None:
            self.manifest_label.setText(_NO_BUNDLE_TEXT)
            self.restore_button.setEnabled(False)
            return
        file_count = len(manifest["apk_files"])
        self.manifest_label.setText(f"{manifest['package']} v{manifest['version_name']} ({file_count} file(s))")
        self.restore_button.setEnabled(True)

    def _on_restore(self):
        if self._current_bundle_dir is None or self._current_manifest is None:
            return
        text = f"Install/replace {self._current_manifest['package']} v{self._current_manifest['version_name']} now?"
        confirm = QMessageBox.question(
            self, "Restore", text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        allow_downgrade = self.allow_downgrade_checkbox.isChecked()
        self.viewmodel.restore(self._current_bundle_dir, allow_downgrade=allow_downgrade)

    def _on_restore_finished(self, manifest):
        self.restore_status_label.setText(f"Restored {manifest['package']} v{manifest['version_name']}.")

    def _on_status(self, message):
        self.backup_status_label.setText(message)
        self.restore_status_label.setText(message)

    def _on_busy(self, busy):
        self.progress_bar.setVisible(busy)
