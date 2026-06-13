"""Transfer module screen (Phase 6.2): pull/push mode toggle, conflict/verify options,
live progress, verification result, and transfer history. Purely declarative - binds
to TransferViewModel signals/slots, no ADB calls or business logic of its own.
"""

from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from droidbridge.core.adb import AdbError
from droidbridge.gui import files_ops
from droidbridge.gui.widgets.remote_browse_dialog import RemoteBrowseDialog
from droidbridge.modules import transfer as transfer_module
from droidbridge.utils.format import format_bytes

_HISTORY_COLUMNS = ("Direction", "Files", "Bytes", "Verified")


class TransferPage(QWidget):
    """Pull/push transfer form bound to TransferViewModel."""

    def __init__(self, viewmodel, parent=None):
        super().__init__(parent)
        self.viewmodel = viewmodel

        self.pull_radio = QRadioButton("Pull (device -> computer)")
        self.push_radio = QRadioButton("Push (computer -> device)")
        self.pull_radio.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.pull_radio)
        self.mode_group.addButton(self.push_radio)

        mode_bar = QHBoxLayout()
        mode_bar.addWidget(self.pull_radio)
        mode_bar.addWidget(self.push_radio)
        mode_bar.addStretch()

        self.remote_path_edit = QLineEdit()
        self.remote_path_browse_button = QPushButton("Browse...")
        self.local_dir_edit = QLineEdit()
        self.local_dir_browse_button = QPushButton("Browse...")

        remote_path_row = QHBoxLayout()
        remote_path_row.addWidget(self.remote_path_edit)
        remote_path_row.addWidget(self.remote_path_browse_button)

        local_dir_row = QHBoxLayout()
        local_dir_row.addWidget(self.local_dir_edit)
        local_dir_row.addWidget(self.local_dir_browse_button)

        self.pull_group = QWidget()
        pull_layout = QFormLayout(self.pull_group)
        pull_layout.addRow("Remote path:", remote_path_row)
        pull_layout.addRow("Local folder:", local_dir_row)

        self.local_path_edit = QLineEdit()
        self.local_file_browse_button = QPushButton("Browse File...")
        self.local_folder_browse_button = QPushButton("Browse Folder...")
        self.remote_dir_edit = QLineEdit()
        self.remote_dir_browse_button = QPushButton("Browse...")
        self.remote_dir_new_folder_button = QPushButton("New Folder...")

        local_path_row = QHBoxLayout()
        local_path_row.addWidget(self.local_path_edit)
        local_path_row.addWidget(self.local_file_browse_button)
        local_path_row.addWidget(self.local_folder_browse_button)

        remote_dir_row = QHBoxLayout()
        remote_dir_row.addWidget(self.remote_dir_edit)
        remote_dir_row.addWidget(self.remote_dir_browse_button)
        remote_dir_row.addWidget(self.remote_dir_new_folder_button)

        self.push_group = QWidget()
        push_layout = QFormLayout(self.push_group)
        push_layout.addRow("Local path:", local_path_row)
        push_layout.addRow("Remote folder:", remote_dir_row)

        self.push_group.setVisible(False)

        self.conflict_combo = QComboBox()
        self.conflict_combo.addItems(transfer_module.CONFLICT_MODES)
        self.conflict_combo.setToolTip(
            "How to handle a destination file that already has the same name "
            "as a source file:\n"
            "Skip: leave the existing file alone.\n"
            "Overwrite: replace it with the source file.\n"
            "Rename: save the source file alongside it with a numeric suffix "
            "(e.g. _1).\n\n"
            "This only applies when the existing file is a different size "
            "than the source (a genuine conflict). If it's already the same "
            "size, it's treated as already transferred (resume) and left "
            "alone regardless of this setting."
        )
        self.verify_checkbox = QCheckBox("Verify after transfer")
        self.verify_checkbox.setChecked(True)

        options_row = QHBoxLayout()
        options_row.addWidget(QLabel("On conflict:"))
        options_row.addWidget(self.conflict_combo)
        options_row.addWidget(self.verify_checkbox)
        options_row.addStretch()

        self.start_button = QPushButton("Start Transfer")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)

        action_row = QHBoxLayout()
        action_row.addWidget(self.start_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch()

        self.plan_label = QLabel()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_label = QLabel()
        self.verification_label = QLabel()

        self.history_table = QTableWidget(0, len(_HISTORY_COLUMNS))
        self.history_table.setHorizontalHeaderLabels(_HISTORY_COLUMNS)
        self.clear_history_button = QPushButton("Clear")

        history_header_row = QHBoxLayout()
        history_header_row.addWidget(QLabel("Transfer History:"))
        history_header_row.addStretch()
        history_header_row.addWidget(self.clear_history_button)

        layout = QVBoxLayout(self)
        layout.addLayout(mode_bar)
        layout.addWidget(self.pull_group)
        layout.addWidget(self.push_group)
        layout.addLayout(options_row)
        layout.addLayout(action_row)
        layout.addWidget(self.plan_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.verification_label)
        layout.addLayout(history_header_row)
        layout.addWidget(self.history_table)

        self.pull_radio.toggled.connect(self.pull_group.setVisible)
        self.push_radio.toggled.connect(self.push_group.setVisible)
        self.local_dir_browse_button.clicked.connect(self._on_browse_local_dir)
        self.local_file_browse_button.clicked.connect(self._on_browse_local_file)
        self.local_folder_browse_button.clicked.connect(self._on_browse_local_folder)
        self.remote_path_browse_button.clicked.connect(self._on_browse_remote_path)
        self.remote_dir_browse_button.clicked.connect(self._on_browse_remote_dir)
        self.remote_dir_new_folder_button.clicked.connect(self._on_new_remote_folder)
        self.start_button.clicked.connect(self._on_start_clicked)
        self.cancel_button.clicked.connect(self.viewmodel.cancel_transfer)
        self.clear_history_button.clicked.connect(self._on_clear_history)

        self.viewmodel.planChanged.connect(self._on_plan_changed)
        self.viewmodel.progressChanged.connect(self._on_progress_changed)
        self.viewmodel.verificationChanged.connect(self._on_verification_changed)
        self.viewmodel.historyEntryAdded.connect(self._on_history_entry_added)
        self.viewmodel.busyChanged.connect(self._on_busy_changed)

    def _on_browse_local_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select destination folder")
        if path:
            self.local_dir_edit.setText(path)

    def _on_browse_local_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select file to push")
        if path:
            self.local_path_edit.setText(path)

    def _on_browse_local_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select folder to push")
        if path:
            self.local_path_edit.setText(path)

    def _on_browse_remote_path(self):
        self._browse_remote(self.remote_path_edit, mode="any")

    def _on_browse_remote_dir(self):
        self._browse_remote(self.remote_dir_edit, mode="directory")

    def _browse_remote(self, line_edit, mode):
        client, serial = self.viewmodel.context.client, self.viewmodel.context.serial
        current = line_edit.text().strip()
        start_path = current if current.startswith("/") else files_ops.QUICK_JUMP_PATHS["Root"]
        path = RemoteBrowseDialog.get_remote_path(self, client, serial, start_path, mode=mode)
        if path:
            line_edit.setText(path)

    def _on_new_remote_folder(self):
        client, serial = self.viewmodel.context.client, self.viewmodel.context.serial
        current = self.remote_dir_edit.text().strip()
        start_path = current if current.startswith("/") else files_ops.QUICK_JUMP_PATHS["Root"]
        parent = RemoteBrowseDialog.get_remote_path(self, client, serial, start_path, mode="directory")
        if not parent:
            return

        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        name = name.strip()
        if not ok or not name:
            return
        if "/" in name:
            QMessageBox.warning(self, "New Folder", "Folder name cannot contain '/'.")
            return

        new_path = files_ops.join_path(parent, name)
        try:
            files_ops.make_directory(client, serial, new_path)
        except AdbError as exc:
            QMessageBox.warning(self, "New Folder", str(exc))
            return
        self.remote_dir_edit.setText(new_path)

    def _on_start_clicked(self):
        conflict = self.conflict_combo.currentText()
        verify = self.verify_checkbox.isChecked()
        if self.pull_radio.isChecked():
            self.viewmodel.start_pull(
                self.remote_path_edit.text().strip(), self.local_dir_edit.text().strip(),
                conflict=conflict, verify=verify,
            )
        else:
            self.viewmodel.start_push(
                self.local_path_edit.text().strip(), self.remote_dir_edit.text().strip(),
                conflict=conflict, verify=verify,
            )

    def _on_plan_changed(self, plan):
        lines = [f"Plan: {plan['total_files']} file(s), {format_bytes(plan['total_bytes'])}."]
        if plan["already_present"]:
            lines.append(f"Skipping {plan['already_present']} file(s) already present (resume).")
        if plan["conflicts_skipped"]:
            lines.append(
                f"Skipping {plan['conflicts_skipped']} file(s) due to conflicts "
                "(use Overwrite or Rename to transfer them)."
            )
        self.plan_label.setText("\n".join(lines))

    def _on_progress_changed(self, progress):
        self.progress_bar.setValue(int(progress["percent"]))
        self.progress_label.setText(
            f"{progress['done_files']}/{progress['total_files']} files | "
            f"{progress['done_bytes_str']} / {progress['total_bytes_str']} | "
            f"{progress['speed_str']} | ETA {progress['eta_str']}"
        )

    def _on_verification_changed(self, verification):
        self.verification_label.setText(verification["message"])
        color = "green" if verification["ok"] else "red"
        self.verification_label.setStyleSheet(f"color: {color};")

    def _on_history_entry_added(self, entry):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        self.history_table.setItem(row, 0, QTableWidgetItem(entry["direction"]))
        self.history_table.setItem(row, 1, QTableWidgetItem(str(entry["total_files"])))
        self.history_table.setItem(row, 2, QTableWidgetItem(format_bytes(entry["total_bytes"])))
        verified = "-" if entry["verification_ok"] is None else ("Yes" if entry["verification_ok"] else "No")
        self.history_table.setItem(row, 3, QTableWidgetItem(verified))

    def _on_clear_history(self):
        self.history_table.setRowCount(0)

    def _on_busy_changed(self, busy):
        self.cancel_button.setVisible(busy)
        self.start_button.setEnabled(not busy)
